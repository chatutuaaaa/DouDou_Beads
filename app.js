const { cloudEnv } = require('./utils/config')

App({
  onLaunch() {
    const projects = wx.getStorageSync('beadProjects') || []
    wx.setStorageSync('beadProjects', projects)

    if (cloudEnv && wx.cloud) {
      wx.cloud.init({ env: cloudEnv, traceUser: true })
    }
  },
  globalData: {
    userInfo: null,
    authUser: null,
    latestPattern: null
  }
})
