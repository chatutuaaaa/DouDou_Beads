const { downloadPatternExport } = require('../../utils/request')
const { enableShareMenu, getPatternShare, getPatternTimelineShare } = require('../../utils/share')

Page({
  data: {
    pattern: null,
    rows: [],
    palette: [],
    selectedColorId: '',
    viewMode: 'mixed',
    cellSize: 20,
    boardWidth: 0,
    boardHeight: 0,
    exporting: false
  },

  onLoad() {
    enableShareMenu()
    const app = getApp()
    const pattern = app.globalData.latestPattern || wx.getStorageSync('latestPattern')

    if (!pattern) {
      wx.showModal({
        title: '暂无图纸',
        content: '请先上传图片生成豆豆图。',
        showCancel: false,
        success: () => wx.redirectTo({ url: '/pages/index/index' })
      })
      return
    }

    app.globalData.latestPattern = pattern
    this.setPattern(pattern)
  },

  setPattern(pattern) {
    const cellSize = this.calculateCellSize(pattern.width)
    const paletteMap = pattern.palette.reduce((result, color) => {
      result[color.id] = color
      return result
    }, {})

    const rows = pattern.grid.map((row, rowIndex) => ({
      key: `row-${rowIndex}`,
      number: rowIndex + 1,
      cells: row.map((colorId, columnIndex) => {
        const color = paletteMap[colorId]
        return {
          key: `${rowIndex}-${columnIndex}`,
          colorId,
          hex: color.hex,
          symbol: color.symbol,
          name: color.name,
          textColor: this.getTextColor(color.rgb)
        }
      })
    }))

    const palette = pattern.palette.map((color) => Object.assign({}, color, {
      percentage: Math.round((color.count / pattern.totalBeads) * 1000) / 10,
      textColor: this.getTextColor(color.rgb)
    }))

    this.setData({
      pattern,
      rows,
      palette,
      cellSize,
      boardWidth: pattern.width * cellSize,
      boardHeight: this.calculateBoardHeight(pattern, cellSize)
    })
  },

  calculateCellSize(width) {
    const safeBoardWidth = 606
    const cellSize = safeBoardWidth / width
    return Math.max(4, cellSize)
  },

  calculateBoardHeight(pattern, cellSize) {
    return pattern.height * cellSize
  },
  setViewMode(event) {
    this.setData({ viewMode: event.currentTarget.dataset.mode })
  },
  selectColor(event) {
    const colorId = event.currentTarget.dataset.colorId
    this.setData({
      selectedColorId: this.data.selectedColorId === colorId ? '' : colorId
    })
  },
  clearFilter() {
    this.setData({ selectedColorId: '' })
  },
  showCellInfo(event) {
    const colorId = event.currentTarget.dataset.colorId
    const color = this.data.palette.find((item) => item.id === colorId)
    if (!color) return
    wx.showToast({
      title: `${color.symbol}`,
      icon: 'none'
    })
  },
  chooseDownload() {
    if (this.data.exporting) return
    wx.showActionSheet({
      itemList: ['保存 PNG 图片', '打开 PDF 图纸'],
      success: (res) => {
        if (res.tapIndex === 0) {
          this.downloadExport('png')
        }
        if (res.tapIndex === 1) {
          this.downloadExport('pdf')
        }
      }
    })
  },
  downloadExport(fileFormat) {
    this.setData({ exporting: true })
    wx.showLoading({ title: fileFormat === 'pdf' ? '生成 PDF' : '生成图片' })
    downloadPatternExport(this.data.pattern.id, fileFormat)
      .then((tempFilePath) => {
        if (fileFormat === 'pdf') {
          this.openPdf(tempFilePath)
          return
        }
        this.saveImage(tempFilePath)
      })
      .catch((error) => {
        wx.showModal({
          title: '下载失败',
          content: error.message || '请稍后重试',
          showCancel: false
        })
      })
      .then(() => {
        wx.hideLoading()
        this.setData({ exporting: false })
      })
  },
  saveImage(tempFilePath) {
    wx.saveImageToPhotosAlbum({
      filePath: tempFilePath,
      success: () => wx.showToast({ title: '已保存到相册', icon: 'success' }),
      fail: () => {
        wx.showModal({
          title: '保存失败',
          content: '请在系统设置中允许小程序访问相册，或重新尝试。',
          showCancel: false
        })
      }
    })
  },
  openPdf(tempFilePath) {
    wx.openDocument({
      filePath: tempFilePath,
      fileType: 'pdf',
      showMenu: true,
      success: () => wx.showToast({ title: 'PDF 已打开', icon: 'none' }),
      fail: () => {
        wx.showModal({
          title: '打开失败',
          content: 'PDF 已生成，但当前环境无法打开文档。请使用真机调试再试。',
          showCancel: false
        })
      }
    })
  },
  copyMaterials() {
    const pattern = this.data.pattern
    const lines = [
      `豆豆图：${pattern.width}×${pattern.height}`,
      `底板：${pattern.board.count} 块 ${pattern.board.size}×${pattern.board.size}`,
      `总豆数：${pattern.totalBeads} 颗`,
      ...this.data.palette.map((color) => `${color.symbol}：${color.count} 颗，建议 ${color.suggestCount} 颗`)
    ]
    wx.setClipboardData({ data: lines.join('\n') })
  },
  getTextColor(rgb) {
    const brightness = (rgb[0] * 299 + rgb[1] * 587 + rgb[2] * 114) / 1000
    return brightness > 150 ? '#2f2a24' : '#ffffff'
  },

  onShareAppMessage() {
    return getPatternShare(this.data.pattern)
  },

  onShareTimeline() {
    return getPatternTimelineShare(this.data.pattern)
  }
})

