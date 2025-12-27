# PlayCap

Docker Playwright を使用したスクリーンショット・キャプチャツール。
Host Proxy 方式により、各プロジェクトの Vite 設定変更なしで動作。

## 特徴

- **Host Proxy**: Vite 開発サーバーへの透過的なプロキシ（設定変更不要）
- **日本語フォント対応**: Mac/Windows スタイルのフォント切り替え
- **認証サポート**: ログイン後のページもキャプチャ可能
- **レスポンシブ対応**: mobile/tablet/desktop の一括キャプチャ

## インストール

```bash
# GitHubからインストール
pip install git+https://github.com/tatun55/playcap.git

# または、ローカルでクローンしてインストール
git clone https://github.com/tatun55/playcap.git
cd playcap
pip install -e .
```

## クイックスタート

```bash
# Docker イメージをビルド（日本語フォント込み）
playcap docker build

# コンテナ起動
playcap docker start

# スクリーンショット撮影
playcap capture page /login

# 認証付きキャプチャ
playcap capture auth /dashboard /profile -e user@example.com -p password

# Mac/Windows フォントで比較キャプチャ
playcap capture platforms /login
```

## コマンド一覧

### グローバルオプション

```bash
playcap --version          # バージョン表示
playcap --config FILE      # 設定ファイルを指定
playcap --verbose          # 詳細ログ出力
```

### キャプチャ

```bash
# 単一ページ
playcap capture page /login
playcap capture page /login --platform mac      # Macフォント
playcap capture page /login --platform windows  # Windowsフォント
playcap capture page /login --viewport mobile   # モバイルサイズ
playcap capture page /login --width 1440 --height 900  # カスタムサイズ
playcap capture page /login --full-page         # フルページ

# 複数ページ（並列）
playcap capture batch /page1 /page2 /page3 --parallel 3

# レスポンシブ（全ビューポート）
playcap capture responsive /login

# プラットフォーム別フォント（Mac + Windows 同時）
playcap capture platforms /login

# 認証付き
playcap capture auth /dashboard /profile -e email -p password
playcap capture auth /dashboard --login-url /admin/login -e admin@example.com -p password
```

### Docker 管理

```bash
playcap docker start    # コンテナ起動
playcap docker stop     # コンテナ停止
playcap docker restart  # コンテナ再起動
playcap docker status   # 状態確認
playcap docker build    # カスタムイメージビルド（フォント込み）
playcap docker build -f # 強制再ビルド
playcap docker logs     # ログ表示
playcap docker logs -f  # ログをフォロー
```

### 設定管理

```bash
playcap config show      # 現在の設定を表示
playcap config init      # .playcap.yaml を生成
playcap config validate  # 設定ファイルを検証
```

## 設定ファイル (.playcap.yaml)

プロジェクトルートに配置すると自動読み込み。

```yaml
version: 1

app:
  base_url: null            # 自動検出（.env の APP_URL）
  env_file: .env
  env_var: APP_URL

proxy:
  enabled: true
  port: 9999
  vite_port: null           # 自動検出

docker:
  playwright_version: "1.48.0"
  container_name: "playcap-playwright"
  ws_port: 3000
  auto_start: true
  auto_stop: false
  use_custom_image: true    # フォント入りイメージを使用
  image_name: "playcap-playwright"

fonts:
  platform: neutral         # neutral, mac, windows
  custom_fonts_dir: null    # カスタムフォントディレクトリ

output:
  directory: "storage/screenshots"
  filename_pattern: "{name}_{date}_{time}.png"
  date_format: "%Y-%m-%d"
  time_format: "%H%M%S"

viewports:
  mobile:
    width: 375
    height: 812
    device_scale_factor: 2
  tablet:
    width: 768
    height: 1024
  desktop:
    width: 1920
    height: 1080

capture:
  default_viewport: desktop
  wait_until: networkidle   # load, domcontentloaded, networkidle
  wait_after: 0             # 追加待機時間(ms)
  full_page: false
```

## アーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│                      Host Machine                            │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │   Valet     │    │    Vite     │    │  PlayCap    │      │
│  │ (PHP App)   │    │ (localhost  │    │   Proxy     │      │
│  │ :80/:443    │    │  :5173)     │    │ (0.0.0.0    │      │
│  └──────┬──────┘    └──────┬──────┘    │  :9999)     │      │
│         │                  │           └──────┬──────┘      │
│         └──────────────────┼──────────────────┤             │
│                            ▼                  ▼             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              host-gateway (Docker bridge)             │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Docker Container                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                 Playwright Browser                   │    │
│  │   - Noto Sans CJK JP (neutral/windows)              │    │
│  │   - Source Han Sans JP (mac)                        │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## 日本語フォント

| プラットフォーム | フォント | 説明 |
|-----------------|---------|------|
| `neutral` | Noto Sans CJK JP | デフォルト、クロスプラットフォーム |
| `mac` | Source Han Sans JP | ヒラギノ角ゴシック風（Adobe製） |
| `windows` | Noto Sans CJK JP | メイリオ風（CSS で font-family 変更） |

カスタムイメージ (`playcap docker build`) には以下がプリインストール:
- **Noto Sans CJK JP** - 全ウェイト（Google製、オープンソース）
- **Source Han Sans JP** - 全ウェイト（Adobe製、オープンソース）

## 動作の仕組み

1. **Host Proxy**: PlayCap は Vite 開発サーバー（localhost:5173）へのプロキシを 0.0.0.0:9999 で起動
2. **Route Interception**: Playwright のルートインターセプションで localhost/0.0.0.0 へのリクエストを host.docker.internal にリダイレクト
3. **CSS Injection**: `--platform` 指定時、ページ読み込み後にフォントファミリーを上書きする CSS を注入

## 要件

- Python 3.8+
- Docker Desktop
- Laravel Valet（推奨、他の開発サーバーでも動作可能）

## トラブルシューティング

### コンテナが起動しない

```bash
# 既存コンテナを削除して再起動
docker rm -f playcap-playwright
playcap docker start
```

### フォントが適用されない

```bash
# カスタムイメージを再ビルド
playcap docker build --force
playcap docker restart
```

### Vite の CSS/JS が読み込まれない

```bash
# Vite 開発サーバーが起動しているか確認
npm run dev

# プロキシが正しいポートを使用しているか確認
playcap config show
```

## ライセンス

MIT
