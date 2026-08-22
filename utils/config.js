// 本地开发：保持 apiBaseUrl，cloudEnv 留空。
// 微信云托管：填入环境 ID 和服务名后，请求走 wx.cloud.callContainer。
const apiBaseUrl = 'http://127.0.0.1:5001'
const cloudEnv = ''
const cloudService = 'doudoutu'

module.exports = {
  apiBaseUrl,
  cloudEnv,
  cloudService
}
