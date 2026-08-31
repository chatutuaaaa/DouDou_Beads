const SHARE_PATH = '/pages/login/login'
const SHARE_IMAGE = '/assets/logo.jpg'

const enableShareMenu = () => {
  if (!wx.showShareMenu) return
  wx.showShareMenu({
    withShareTicket: true,
    menus: ['shareAppMessage', 'shareTimeline']
  })
}

const getDefaultShare = () => ({
  title: '豆豆图｜把照片变成拼豆图纸',
  path: SHARE_PATH,
  imageUrl: SHARE_IMAGE
})

const getDefaultTimelineShare = () => ({
  title: '豆豆图｜把照片变成拼豆图纸',
  query: '',
  imageUrl: SHARE_IMAGE
})

const getPatternShare = (pattern) => ({
  title: pattern ? `我生成了一张 ${pattern.width}×${pattern.height} 豆豆图` : getDefaultShare().title,
  path: SHARE_PATH,
  imageUrl: SHARE_IMAGE
})

const getPatternTimelineShare = (pattern) => ({
  title: pattern ? `我生成了一张 ${pattern.width}×${pattern.height} 豆豆图` : getDefaultTimelineShare().title,
  query: '',
  imageUrl: SHARE_IMAGE
})

module.exports = {
  enableShareMenu,
  getDefaultShare,
  getDefaultTimelineShare,
  getPatternShare,
  getPatternTimelineShare
}
