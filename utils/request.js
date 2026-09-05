const { apiBaseUrl, cloudEnv, cloudService } = require('./config')

const NET_ERR = '网络异常，请稍后重试'
const JSON_ERR = '后端返回格式不是 JSON'

const isCloudMode = () => !!cloudEnv

const normalizeError = (error) => {
  if (typeof error === 'string') return new Error(error)
  if (error && error.message) return error
  if (error && error.errMsg) return new Error(error.errMsg)
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

const assertSuccess = (body, statusCode) => {
  if (statusCode < 200 || statusCode >= 300 || !body || body.code !== 0) {
    throw new Error((body && body.message) || `接口异常：${statusCode}`)
  }
  return body.data
}

// ---------- HTTP (local) ----------
const httpJson = (options) => new Promise((resolve, reject) => {
  wx.request({
    url: `${apiBaseUrl}${options.url}`,
    method: options.method || 'GET',
    data: options.data || {},
    header: Object.assign({ 'content-type': 'application/json' }, options.header || {}),
    success: (res) => {
      try { resolve(assertSuccess(parseResponse(res.data), res.statusCode)) }
      catch (e) { reject(e) }
    },
    fail: (error) => reject(normalizeError(error))
  })
})

const callContainer = (options) => new Promise((resolve, reject) => {
  wx.cloud.callContainer({
    config: { env: cloudEnv },
    path: options.url,
    method: options.method || 'GET',
    data: options.data || {},
    header: Object.assign(
      { 'content-type': 'application/json', 'X-WX-SERVICE': cloudService },
      options.header || {}
    ),
    success: (res) => {
      try { resolve(assertSuccess(parseResponse(res.data), res.statusCode)) }
      catch (e) { reject(e) }
    },
    fail: (error) => reject(normalizeError(error))
  })
})

const requestJson = (options) => isCloudMode() ? callContainer(options) : httpJson(options)

const cloudExtname = (filePath) => {
  const match = String(filePath || '').match(/\.([a-zA-Z0-9]+)(?:\?|$)/)
  return match ? match[1].toLowerCase() : 'jpg'
}

const uploadImageToCloud = (filePath) => new Promise((resolve, reject) => {
  const ext = cloudExtname(filePath)
  const random = Math.random().toString(36).slice(2, 10)
  const cloudPath = `uploads/${Date.now()}-${random}.${ext}`

  wx.cloud.uploadFile({
    cloudPath,
    filePath,
    success: (res) => resolve(res.fileID),
    fail: (error) => reject(normalizeError(error))
  })
})

const getTempImageUrl = (fileID) => new Promise((resolve, reject) => {
  wx.cloud.getTempFileURL({
    fileList: [fileID],
    success: (res) => {
      const item = res.fileList && res.fileList[0]
      if (!item || item.status !== 0 || !item.tempFileURL) {
        reject(new Error((item && item.errMsg) || '获取图片临时链接失败'))
        return
      }
      resolve(item.tempFileURL)
    },
    fail: (error) => reject(normalizeError(error))
  })
})

const deleteCloudImage = (fileID) => new Promise((resolve) => {
  if (!fileID) {
    resolve()
    return
  }
  wx.cloud.deleteFile({
    fileList: [fileID],
    success: () => resolve(),
    fail: () => resolve()
  })
})

// ---------- hot comment ----------
const fetchHotComment = () => requestJson({
  url: '/api/hot-comment',
  method: 'GET'
}).then((data) => data.comment)

// ---------- generate ----------
const generatePattern = (filePath, formData) => {
  if (isCloudMode()) {
    return uploadImageToCloud(filePath)
      .then((fileID) => getTempImageUrl(fileID)
        .then((imageUrl) => callContainer({
          url: '/api/generate',
          method: 'POST',
          data: {
            imageUrl,
            imageFileID: fileID,
            width: formData.width,
            height: formData.height,
            max_colors: formData.max_colors,
            mode: formData.mode,
            palette: formData.palette
          }
        }))
        .then((result) => deleteCloudImage(fileID).then(() => result))
        .catch((error) => deleteCloudImage(fileID).then(() => { throw error })))
  }

  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: `${apiBaseUrl}/api/generate`,
      filePath,
      name: 'image',
      formData,
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
  callContainer,
  downloadPatternExport,
  fetchHotComment,
  generatePattern,
  isCloudMode,
  requestJson
}
