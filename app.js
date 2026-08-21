App({
  onLaunch() {
    const projects = wx.getStorageSync('beadProjects') || []
    wx.setStorageSync('beadProjects', projects)
  },
  globalData: {
    userInfo: null,
    authUser: null,
    latestPattern: null
  }
})
