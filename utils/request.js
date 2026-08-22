const { apiBaseUrl, cloudEnv, cloudService } = require('./config')

const TOKEN_KEY = 'authToken'
const USER_KEY = 'authUser'

const NET_ERR = '\u7f51\u7edc\u5f02\u5e38\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5'
const JSON_ERR = '\u540e\u7aef\u8fd4\u56de\u683c\u5f0f\u4e0d\u662f JSON'

const isCloudMode = () => !!cloudEnv

const normalizeError = (error) => {
  if (typeof error === 'string') return new Error(error)
  if (error && error.message) return error
  return new Error(NET_ERR)
}

const parseResponse = (rawData) => {
  if (typeof rawData === 'string') {
    try {
      return JSON.parse(rawData)
    } catch (error) {
      throw new Error(JSON_ERR)
    }
  }
  return rawData
}

const getAuthToken = () => wx.getStorageSync(TOKEN_KEY) || ''
const getStoredUser = () => wx.getStorageSync(USER_KEY) || null

const setAuth = (auth) => {
  wx.setStorageSync(TOKEN_KEY, auth.token)
  wx.setStorageSync(USER_KEY, auth.user)
}

const clearAuth = () => {
  wx.removeStorageSync(TOKEN_KEY)
  wx.removeStorageSync(USER_KEY)
}

const assertSuccess = (body, statusCode) => {
  if (statusCode < 200 || statusCode >= 300 || !body || body.code !== 0) {
    throw new Error((body && body.message) || `\u63a5\u53e3\u5f02\u5e38\uff1a${statusCode}`)
  }
  return body.data
}

// ---------- HTTP (local) ----------
const httpJson = (options) => new Promise((resolve, reject) => {
  const token = getAuthToken()
  const header = Object.assign({ 'content-type': 'application/json' }, options.header || {})
  if (token) header.Authorization = `Bearer ${token}`

  wx.request({
    url: `${apiBaseUrl}${options.url}`,
    method: options.method || 'GET',
    data: options.data || {},
    header,
    success: (res) => {
      try { resolve(assertSuccess(parseResponse(res.data), res.statusCode)) }
      catch (e) { reject(e) }
    },
    fail: (error) => reject(normalizeError(error))
  })
})

const callContainer = (options) => new Promise((resolve, reject) => {
  const header = Object.assign(
    { 'content-type': 'application/json', 'X-WX-SERVICE': cloudService },
    options.header || {}
  )
  wx.cloud.callContainer({
    config: { env: cloudEnv },
    path: options.url,
    method: options.method || 'GET',
    data: options.data || {},
    header,
    success: (res) => {
      try { resolve(assertSuccess(parseResponse(res.data), res.statusCode)) }
      catch (e) { reject(e) }
    },
    fail: (error) => reject(normalizeError(error))
  })
})

const requestJson = (options) => isCloudMode() ? callContainer(options) : httpJson(options)

// ---------- login ----------
const loginWithWechat = (profile) => {
  if (isCloudMode()) {
    const auth = { token: 'cloud', user: cloudUser() }
    setAuth(auth)
    return Promise.resolve(auth)
  }
  return new Promise((resolve, reject) => {
    wx.login({
      success: (loginRes) => {
        if (!loginRes.code) {
          reject(new Error('\u5fae\u4fe1\u767b\u5f55\u5931\u8d25\uff0c\u672a\u83b7\u53d6\u5230 code'))
          return
        }
        requestJson({
          url: '/api/auth/login',
          method: 'POST',
          data: Object.assign({ code: loginRes.code }, profile || {})
        }).then((auth) => { setAuth(auth); resolve(auth) }).catch(reject)
      },
      fail: (error) => reject(normalizeError(error))
    })
  })
}

const cloudUser = () => ({
  openidMasked: 'cloud-user',
  nickname: '\u8c46\u8c46\u56fe\u7528\u6237',
  avatarUrl: '',
  isCloud: true
})

const updateProfile = (profile) => requestJson({
  url: '/api/auth/profile', method: 'POST', data: profile || {}
}).then((data) => {
  const auth = { token: getAuthToken(), user: data.user }
  setAuth(auth)
  return data.user
})

// ---------- generate ----------
const readFileAsBase64 = (filePath) => new Promise((resolve, reject) => {
  wx.getFileSystemManager().readFile({
    filePath,
    encoding: 'base64',
    success: (res) => resolve(res.data),
    fail: reject
  })
})

const generatePattern = (filePath, formData) => {
  if (isCloudMode()) {
    return readFileAsBase64(filePath).then((b64) => callContainer({
      url: '/api/generate',
      method: 'POST',
      data: {
        image: `data:image/jpeg;base64,${b64}`,
        width: formData.width,
        height: formData.height,
        max_colors: formData.max_colors,
        mode: formData.mode,
        palette: formData.palette
      }
    }))
  }

  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: `${apiBaseUrl}/api/generate`,
      filePath,
      name: 'image',
      formData,
      header: { Authorization: `Bearer ${getAuthToken()}` },
      success: (res) => {
        try { resolve(assertSuccess(parseResponse(res.data), res.statusCode)) }
        catch (e) { reject(e) }
      },
      fail: (error) => reject(normalizeError(error))
    })
  })
}

// ---------- export ----------
const downloadPatternExport = (patternId, fileFormat) => {
  if (isCloudMode()) {
    return callContainer({
      url: `/api/patterns/${patternId}/export-base64?format=${fileFormat}`,
      method: 'GET'
    }).then((data) => new Promise((resolve, reject) => {
      const ext = fileFormat === 'pdf' ? 'pdf' : 'png'
      const filePath = `${wx.env.USER_DATA_PATH}/doudoutu-${patternId}.${ext}`
      wx.getFileSystemManager().writeFile({
        filePath,
        data: data.dataBase64,
        encoding: 'base64',
        success: () => resolve(filePath),
        fail: reject
      })
    }))
  }

  return new Promise((resolve, reject) => {
    wx.downloadFile({
      url: `${apiBaseUrl}/api/patterns/${patternId}/export?format=${fileFormat}`,
      header: { Authorization: `Bearer ${getAuthToken()}` },
      success: (res) => {
        if (res.statusCode < 200 || res.statusCode >= 300) {
          reject(new Error(`\u5bfc\u51fa\u5931\u8d25\uff1a${res.statusCode}`))
          return
        }
        resolve(res.tempFilePath)
      },
      fail: (error) => reject(normalizeError(error))
    })
  })
}

module.exports = {
  callContainer,
  clearAuth,
  downloadPatternExport,
  generatePattern,
  getAuthToken,
  getStoredUser,
  isCloudMode,
  loginAsGuest: () => requestJson({ url: '/api/auth/guest', method: 'POST', data: {} }).then((auth) => { setAuth(auth); return auth }),
  isTrialExhausted: (error) => !!error && error.message === '\u8bd5\u7528\u6b21\u6570\u5df2\u7528\u5b8c\uff0c\u8bf7\u767b\u5f55\u540e\u7ee7\u7eed\u4f7f\u7528',
  loginWithWechat,
  requestJson,
  updateProfile
}
