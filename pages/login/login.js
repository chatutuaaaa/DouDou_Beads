const { getStoredUser, loginAsGuest, loginWithWechat, isTrialExhausted } = require('../../utils/request')

const defaultAvatarText = '豆'

Page({
  data: {
    avatarUrl: '',
    nickname: '',
    loggingIn: false,
    defaultAvatarText
  },

  onShow() {
    const user = getStoredUser()
    if (user) {
      getApp().globalData.authUser = user
      wx.reLaunch({ url: '/pages/index/index' })
    }
  },

  onChooseAvatar(event) {
    const avatarUrl = event.detail.avatarUrl
    if (!avatarUrl) return

    this.setData({ avatarUrl })
  },

  onNicknameInput(event) {
    this.setData({ nickname: event.detail.value })
  },

  syncWechatProfile() {
    this.getWechatProfile()
      .then(() => wx.showToast({ title: '已同步微信资料', icon: 'none' }))
      .catch(() => wx.showToast({ title: '可手动设置头像昵称', icon: 'none' }))
  },

  getWechatProfile() {
    return new Promise((resolve, reject) => {
      if (!wx.getUserProfile) {
        reject(new Error('当前基础库不支持同步'))
        return
      }

      wx.getUserProfile({
        desc: '用于展示头像昵称',
        success: (res) => {
          const profile = {
            avatarUrl: res.userInfo.avatarUrl || this.data.avatarUrl,
            nickname: res.userInfo.nickName || this.data.nickname
          }
          this.setData(profile)
          resolve(profile)
        },
        fail: reject
      })
    })
  },

  login() {
    if (this.data.loggingIn) return

    this.setData({ loggingIn: true })
    wx.showLoading({ title: '正在登录' })

    const currentProfile = {
      avatarUrl: this.data.avatarUrl,
      nickname: this.data.nickname
    }
    const profilePromise = currentProfile.avatarUrl || currentProfile.nickname
      ? Promise.resolve(currentProfile)
      : this.getWechatProfile().catch(() => currentProfile)

    profilePromise
      .then((profile) => loginWithWechat(profile))
      .then((auth) => {
        getApp().globalData.authUser = auth.user
        wx.reLaunch({ url: '/pages/index/index' })
      })
      .catch((error) => {
        wx.showModal({
          title: '登录失败',
          content: error.message || '请稍后重试',
          showCancel: false
        })
      })
      .then(() => {
        wx.hideLoading()
        this.setData({ loggingIn: false })
      })
  },

  loginAsGuest() {
    if (this.data.loggingIn) return
    this.setData({ loggingIn: true })
    wx.showLoading({ title: '\u8bd5\u7528\u4e2d' })
    loginAsGuest()
      .then((auth) => {
        getApp().globalData.authUser = auth.user
        wx.reLaunch({ url: '/pages/index/index' })
      })
      .catch((error) => {
        wx.showModal({
          title: '\u8bd5\u7528\u5931\u8d25',
          content: error.message || '\u7f51\u7edc\u5f02\u5e38\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5',
          showCancel: false
        })
      })
      .then(() => {
        wx.hideLoading()
        this.setData({ loggingIn: false })
      })
  }

})
