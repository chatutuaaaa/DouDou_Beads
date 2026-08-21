# 拼豆图纸生成器 MVP

这是一个微信小程序原生前端 + Python Flask 后端的第一版拼豆图纸生成器。

## 功能

- 微信登录后使用，后端按 `openid` 统计用户数量
- 登录时可同步微信头像昵称，也可在首页自定义头像和昵称
- 上传相册或拍摄图片
- 选择 `29×29` 或 `58×58` 成品尺寸
- 选择最多 `8/12/16/24` 色
- 后端自动裁剪、像素化、限色并匹配 Artkal-S 色卡
- 小程序展示彩色网格、符号网格、分板信息和材料清单
- 支持点击颜色高亮、复制材料清单
- 支持导出包含完整图纸和色块清单的 PNG 图片或 PDF 文件

## 启动后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

默认接口地址是 `http://127.0.0.1:5001`，可在 `utils/config.js` 修改。

## 微信登录配置

小程序端通过 `wx.login()` 获取临时 `code`，后端使用 `code2Session` 换取当前小程序下的用户唯一标识 `openid`。微信不会向小程序直接提供用户真实微信号，统计用户数量应使用 `openid`。

本地未配置密钥时，后端会自动使用模拟 `openid`，方便开发联调。上线前请配置环境变量：

```bash
export WECHAT_APPID="你的小程序 AppID"
export WECHAT_SECRET="你的小程序 AppSecret"
export FLASK_SECRET_KEY="用于签发登录 token 的随机长字符串"
export ADMIN_TOKEN="查看统计接口用的管理密钥"
```

用户数据默认保存在 `backend/data/app.db`。

## 本地调试小程序

1. 用微信开发者工具导入当前目录。
2. 开启 Flask 后端。
3. 本地开发时在开发者工具勾选“不校验合法域名、web-view、TLS 版本以及 HTTPS 证书”。
4. 真机和上线前，将 Flask 部署到 HTTPS 域名，并在小程序后台配置 request/uploadFile 合法域名。

## 接口

### `POST /api/generate`

需要请求头：

```text
Authorization: Bearer <登录后返回的 token>
```

表单字段：

- `image`：上传图片文件
- `width`：图纸宽度，当前前端传 `29` 或 `58`
- `height`：图纸高度，当前前端传 `29` 或 `58`
- `max_colors`：最多颜色数
- `mode`：`clean` 或 `natural`
- `palette`：当前默认为 `artkal_s`

返回字段包含：

- `grid`：二维颜色编号矩阵
- `palette`：实际使用颜色、符号、数量和建议备货数
- `board`：29×29 底板切分信息
- `totalBeads`：总豆数

### `GET /api/patterns/<pattern_id>/export?format=png|pdf`

导出完整图纸文件，包含网格图纸、底板分割线和色块清单。

需要请求头：

```text
Authorization: Bearer <登录后返回的 token>
```

小程序端点击“下载图纸”后可选择：

- 保存 PNG 图片到相册
- 打开 PDF 图纸，并通过右上角菜单转发或保存

### `POST /api/auth/login`

请求 JSON：

```json
{
  "code": "wx.login 返回的 code"
}
```

返回登录 `token` 和脱敏用户信息。

### `GET /api/admin/stats`

返回用户总数。若配置了 `ADMIN_TOKEN`，需要请求头：

```text
X-Admin-Token: <ADMIN_TOKEN>
```
