const { generatePattern, ensureAuthUser, isTrialExhausted, clearAuth } = require('../../utils/request')
const { apiBaseUrl } = require('../../utils/config')

const defaultAvatarText = '豆'

Page({
  data: {
    imagePath: '',
    imageName: '',
    sizeOptions: [
      { label: '29 × 29', desc: '一块板｜新手推荐', width: 29, height: 29 },
      { label: '58 × 58', desc: '四块板｜细节更好', width: 58, height: 58 }
    ],
    colorOptions: [8, 12, 16, 24],
    styleOptions: [
      { label: '清晰像素风', value: 'clean', desc: '边缘更明确' },
      { label: '真实还原风', value: 'natural', desc: '更接近原图' }
    ],
    selectedSizeIndex: 0,
    selectedColorIndex: 1,
    selectedStyleIndex: 0,
    generating: false,
    user: null,
    defaultAvatarText,
    apiBaseUrl
  },

  onShow() {
    const user = ensureAuthUser()
    if (!user) {
      wx.reLaunch({ url: '/pages/login/login' })
      return
    }

    this.setData({ user })
    getApp().globalData.authUser = user
  },

  chooseImage() {
    if (!this.data.user) {
      wx.reLaunch({ url: '/pages/login/login' })
      return
    }

    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      sizeType: ['compressed'],
      success: (res) => {
        const file = res.tempFiles && res.tempFiles[0]
        if (!file) return

        this.setData({
          imagePath: file.tempFilePath,
          imageName: this.getFileName(file.tempFilePath)
        })
      }
    })
  },

  selectSize(event) {
    this.setData({ selectedSizeIndex: Number(event.currentTarget.dataset.index) })
  },

  selectColor(event) {
    this.setData({ selectedColorIndex: Number(event.currentTarget.dataset.index) })
  },

  selectStyle(event) {
    this.setData({ selectedStyleIndex: Number(event.currentTarget.dataset.index) })
  },

  submitGenerate() {
    if (!this.data.user) {
      wx.reLaunch({ url: '/pages/login/login' })
      return
    }

    if (!this.data.imagePath) {
      wx.showToast({ title: '请先上传图片', icon: 'none' })
      return
    }

    const size = this.data.sizeOptions[this.data.selectedSizeIndex]
    const maxColors = this.data.colorOptions[this.data.selectedColorIndex]
    const mode = this.data.styleOptions[this.data.selectedStyleIndex].value
    const finish = () => {
      wx.hideLoading()
      this.setData({ generating: false })
    }

    this.setData({ generating: true })
    wx.showLoading({ title: '正在生成图纸' })

    generatePattern(this.data.imagePath, {
      width: size.width,
      height: size.height,
      max_colors: maxColors,
      mode,
      palette: 'mard_221'
    })
      .then((pattern) => {
        const projects = wx.getStorageSync('beadProjects') || []
        const project = {
          id: pattern.id,
          createdAt: pattern.createdAt,
          imagePath: this.data.imagePath,
          pattern
        }

        projects.unshift(project)
        wx.setStorageSync('latestPattern', pattern)
        wx.setStorageSync('beadProjects', projects.slice(0, 20))

        if (typeof pattern.trialRemaining === 'number') {
          this.updateTrialRemaining(pattern.trialRemaining)
          if (pattern.trialRemaining <= 0) {
            wx.showToast({ title: '\u8bd5\u7528\u5df2\u7528\u5b8c', icon: 'none' })
          } else {
            wx.showToast({ title: '\u8fd8\u53ef\u8bd5\u7528 ' + pattern.trialRemaining + ' \u6b21', icon: 'none' })
          }
        }
        wx.navigateTo({ url: '/pages/preview/preview' })
        finish()
      })
      .catch((error) => {
        if (isTrialExhausted(error)) {
          clearAuth()
          wx.showModal({
            title: '\u8bd5\u7528\u6b21\u6570\u5df2\u7528\u5b8c',
            content: '\u767b\u5f55\u540e\u5373\u53ef\u7ee7\u7eed\u751f\u6210\u56fe\u7eb8\u3002',
            confirmText: '\u53bb\u767b\u5f55',
            showCancel: false,
            success: () => wx.reLaunch({ url: '/pages/login/login' })
          })
          finish()
          return
        }
        wx.showModal({
          title: '生成失败',
          content: error.message || '请确认 Flask 后端已启动，并检查接口地址。',
          showCancel: false
        })
        finish()
      })
  },

  getFileName(path) {
    const parts = path.split('/')
    return parts[parts.length - 1] || '已选择图片'
  },

  updateTrialRemaining(remaining) {
    const user = this.data.user
    if (!user || !user.isGuest) return
    const updated = Object.assign({}, user, { trialRemaining: remaining, trialUsed: user.trialLimit - remaining })
    this.setData({ user: updated })
    wx.setStorageSync('authUser', updated)
    getApp().globalData.authUser = updated
  },

  goLogin() {
    clearAuth()
    wx.reLaunch({ url: '/pages/login/login' })
  }

})
