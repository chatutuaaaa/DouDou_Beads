const { apiBaseUrl } = require('./config')

const TOKEN_KEY = 'authToken'
const USER_KEY = 'authUser'

const normalizeError = (error) => {
  if (typeof error === 'string') return new Error(error)
  if (error && error.message) return error
  return new Error('网络异常，请稍后重试')
}

const parseResponse = (rawData) => {
  if (typeof rawData === 'string') {
    try {
      return JSON.parse(rawData)
    } catch (error) {
      throw new Error('后端返回格式不是 JSON')
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

const requestJson = (options) => {
  return new Promise((resolve, reject) => {
    const token = getAuthToken()
    const header = Object.assign({
      'content-type': 'application/json'
    }, options.header || {})

    if (token) {
      header.Authorization = `Bearer ${token}`
    }

    wx.request({
      url: `${apiBaseUrl}${options.url}`,
      method: options.method || 'GET',
      data: options.data || {},
      header,
      success: (res) => {
        const body = parseResponse(res.data)

        if (res.statusCode < 200 || res.statusCode >= 300 || body.code !== 0) {
          reject(new Error(body.message || `接口异常：${res.statusCode}`))
          return
        }

        resolve(body.data)
      },
      fail: (error) => reject(normalizeError(error))
    })
  })
}

const loginWithWechat = (profile) => {
  return new Promise((resolve, reject) => {
    wx.login({
      success: (loginRes) => {
        if (!loginRes.code) {
          reject(new Error('微信登录失败，未获取到 code'))
          return
        }

        requestJson({
          url: '/api/auth/login',
          method: 'POST',
          data: Object.assign({ code: loginRes.code }, profile || {})
        })
          .then((auth) => {
            setAuth(auth)
            resolve(auth)
          })
          .catch(reject)
      },
      fail: (error) => reject(normalizeError(error))
    })
  })
}

const updateProfile = (profile) => {
  return requestJson({
    url: '/api/auth/profile',
    method: 'POST',
    data: profile || {}
  }).then((data) => {
    const auth = {
      token: getAuthToken(),
      user: data.user
    }
    setAuth(auth)
    return data.user
  })
}

const generatePattern = (filePath, formData) => {
  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: `${apiBaseUrl}/api/generate`,
      filePath,
      name: 'image',
      formData,
      header: {
        Authorization: `Bearer ${getAuthToken()}`
      },
      success: (res) => {
        try {
          const body = parseResponse(res.data)

          if (res.statusCode < 200 || res.statusCode >= 300) {
            reject(new Error(body.message || `接口异常：${res.statusCode}`))
            return
          }

          if (body.code !== 0) {
            reject(new Error(body.message || '图纸生成失败'))
            return
          }

          resolve(body.data)
        } catch (error) {
          reject(normalizeError(error))
        }
      },
      fail: (error) => {
        reject(normalizeError(error))
      }
    })
  })
}

const downloadPatternExport = (patternId, fileFormat) => {
  return new Promise((resolve, reject) => {
    wx.downloadFile({
      url: `${apiBaseUrl}/api/patterns/${patternId}/export?format=${fileFormat}`,
      header: {
        Authorization: `Bearer ${getAuthToken()}`
      },
      success: (res) => {
        if (res.statusCode < 200 || res.statusCode >= 300) {
          reject(new Error(`导出失败：${res.statusCode}`))
          return
        }

        resolve(res.tempFilePath)
      },
      fail: (error) => reject(normalizeError(error))
    })
  })
}

module.exports = {
  clearAuth,
  downloadPatternExport,
  generatePattern,
  getAuthToken,
  getStoredUser,
  loginWithWechat,
  updateProfile
}
