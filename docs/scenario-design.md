# Shayde Scenario 機能設計書

## 概要

YAMLベースのE2Eシナリオを対話的に実行し、各ステップでスクリーンショットを撮影する機能。

## アーキテクチャ

```
┌─────────────────────────────────────────────────────────┐
│  shayde scenario CLI                                    │
│  ├── parse   - シナリオ解析                             │
│  ├── list    - ステップ一覧                             │
│  ├── run     - 全ステップ実行                           │
│  ├── step    - 単一ステップ実行                         │
│  └── report  - レポート生成                             │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  core/scenario/                                         │
│  ├── parser.py      - YAMLパーサー                      │
│  ├── runner.py      - ScenarioRunner (ステップ実行)     │
│  ├── actions.py     - Playwrightアクション実行          │
│  ├── assertions.py  - 検証ロジック                      │
│  ├── session.py     - セッション管理 (認証状態保持)     │
│  └── reporter.py    - レポート生成                      │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  既存のCaptureSession (core/capture.py)                 │
│  - Playwright接続                                       │
│  - Docker管理                                           │
│  - スクリーンショット撮影                               │
└─────────────────────────────────────────────────────────┘
```

## ファイル構造

```
src/shayde/
├── cli/
│   ├── main.py          # scenarioを追加
│   └── scenario.py      # CLIコマンド (新規)
├── core/
│   ├── capture.py       # 既存
│   └── scenario/        # 新規ディレクトリ
│       ├── __init__.py
│       ├── parser.py    # YAMLパーサー
│       ├── runner.py    # ステップ実行エンジン
│       ├── actions.py   # アクション実行
│       ├── assertions.py # 検証ロジック
│       ├── session.py   # セッション管理
│       └── reporter.py  # レポート生成
└── schemas/
    └── scenario.schema.json  # JSONスキーマ (バリデーション用)
```

## CLI コマンド

### `shayde scenario parse <file>`

シナリオファイルを解析し、構造をJSON出力。

```bash
shayde scenario parse scenarios/01-authentication.yaml
# Output: JSON形式でステップ一覧

shayde scenario parse scenarios/01-authentication.yaml --validate
# Output: バリデーション結果
```

### `shayde scenario list <file>`

ステップ一覧をフォーマット表示。

```bash
shayde scenario list scenarios/01-authentication.yaml

# Output:
# 01-authentication: 認証・アクセス制御フロー
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Part 1: 未認証アクセス制御 (account: none)
#   [1-1] 管理画面URLにアクセス         📸
#   [1-2] URLバー確認
# Part 2: ログイン失敗 (account: none)
#   [2-1] メールアドレス入力
#   [2-2] 誤ったパスワード入力
#   [2-3] ログインボタンクリック        📸
# ...
# Total: 15 steps, 8 screenshots
```

### `shayde scenario run <file>`

全ステップを実行。

```bash
# 全自動実行
shayde scenario run scenarios/01-authentication.yaml

# エラー時に停止
shayde scenario run scenarios/01-authentication.yaml --stop-on-error

# 特定Partのみ
shayde scenario run scenarios/01-authentication.yaml --part 2

# 出力ディレクトリ指定
shayde scenario run scenarios/01-authentication.yaml -o storage/screenshots/e2e
```

### `shayde scenario step <file> <step_id>`

単一ステップを実行。

```bash
# ステップ1-1を実行
shayde scenario step scenarios/01-authentication.yaml 1-1

# セッションを引き継ぐ（前ステップの状態を維持）
shayde scenario step scenarios/01-authentication.yaml 2-3 --session session_abc123
```

### `shayde scenario report <dir>`

実行結果からレポートを生成。

```bash
shayde scenario report storage/screenshots/e2e/01-authentication_2025-12-29
# Output: report.md を生成
```

## スクリーンショット出力構造

```
storage/screenshots/e2e/
└── {scenario_id}_{YYYY-MM-DD}/
    ├── part-01_未認証アクセス制御/
    │   ├── step-1-1_管理画面URLにアクセス.png
    │   └── step-1-2_URLバー確認.png
    ├── part-02_ログイン失敗/
    │   ├── step-2-1_メールアドレス入力.png
    │   └── step-2-3_ログインボタンクリック.png
    ├── part-03_ログイン成功/
    │   └── step-3-3_ログイン完了.png
    ├── results.json          # 実行結果データ
    └── report.md             # Markdownレポート
```

### ファイル命名規則

| 要素 | フォーマット | 例 |
|------|-------------|-----|
| ディレクトリ | `{scenario_id}_{date}` | `01-authentication_2025-12-29` |
| Partディレクトリ | `part-{nn}_{title_sanitized}` | `part-01_未認証アクセス制御` |
| スクリーンショット | `step-{id}_{desc_sanitized}.png` | `step-1-1_管理画面URLにアクセス.png` |

### results.json 構造

```json
{
  "scenario_id": "01-authentication",
  "title": "認証・アクセス制御フロー",
  "started_at": "2025-12-29T10:30:00",
  "completed_at": "2025-12-29T10:35:00",
  "status": "passed",
  "parts": [
    {
      "part": 1,
      "title": "未認証アクセス制御",
      "status": "passed",
      "steps": [
        {
          "id": "1-1",
          "desc": "管理画面URLにアクセス",
          "status": "passed",
          "screenshot": "part-01_未認証アクセス制御/step-1-1_管理画面URLにアクセス.png",
          "duration_ms": 1200,
          "assertions": [
            { "type": "url", "expected": "/login", "actual": "/login", "passed": true }
          ]
        }
      ]
    }
  ],
  "summary": {
    "total_steps": 15,
    "passed": 15,
    "failed": 0,
    "skipped": 0,
    "duration_ms": 45000
  }
}
```

## アクション実行

### actions.py

```python
class ActionExecutor:
    """Playwrightアクションを実行"""

    async def execute(self, page: Page, action: dict) -> ActionResult:
        """アクションを実行"""
        pass

    async def goto(self, page: Page, url: str, wait: str = None) -> ActionResult:
        """ページ遷移"""
        pass

    async def fill(self, page: Page, selector: str, value: str) -> ActionResult:
        """入力"""
        pass

    async def click(self, page: Page, selector: str, wait: str = None) -> ActionResult:
        """クリック"""
        pass

    async def select(self, page: Page, selector: str, value: str) -> ActionResult:
        """セレクト選択"""
        pass

    async def upload(self, page: Page, selector: str, file: str) -> ActionResult:
        """ファイルアップロード"""
        pass

    async def clear(self, page: Page, selector: str) -> ActionResult:
        """入力欄クリア"""
        pass

    async def login(self, page: Page, account_key: str, accounts: dict) -> ActionResult:
        """認証ショートカット"""
        pass

    async def logout(self, page: Page) -> ActionResult:
        """ログアウト"""
        pass
```

### assertions.py

```python
class AssertionExecutor:
    """検証ロジックを実行"""

    async def verify(self, page: Page, expect: dict) -> AssertionResult:
        """検証を実行"""
        pass

    async def url(self, page: Page, expected: str) -> AssertionResult:
        """URL完全一致"""
        pass

    async def url_contains(self, page: Page, expected: str) -> AssertionResult:
        """URL部分一致"""
        pass

    async def visible(self, page: Page, selector: str) -> AssertionResult:
        """要素表示確認"""
        pass

    async def hidden(self, page: Page, selector: str) -> AssertionResult:
        """要素非表示確認"""
        pass

    async def text_contains(self, page: Page, text: str, selector: str = None) -> AssertionResult:
        """テキスト含有確認"""
        pass

    async def value(self, page: Page, selector: str, expected: str) -> AssertionResult:
        """入力値確認"""
        pass
```

## セッション管理

### session.py

```python
class ScenarioSession:
    """シナリオ実行セッション管理"""

    def __init__(self, scenario_id: str, output_dir: Path):
        self.session_id = generate_session_id()
        self.scenario_id = scenario_id
        self.output_dir = output_dir
        self.current_account = None
        self.browser_context = None
        self.results = []

    async def switch_account(self, account_key: str, accounts: dict):
        """アカウント切り替え（ログイン状態変更）"""
        pass

    async def get_page(self) -> Page:
        """現在のページを取得"""
        pass

    def get_screenshot_path(self, part: int, part_title: str, step_id: str, step_desc: str) -> Path:
        """スクリーンショットパスを生成"""
        pass

    def record_result(self, step_id: str, result: StepResult):
        """結果を記録"""
        pass

    def save_results(self):
        """results.json を保存"""
        pass
```

## レポート生成

### report.md テンプレート

```markdown
# {title} - 実行レポート

**実行日時**: {started_at}
**所要時間**: {duration}
**結果**: {status_emoji} {status}

## サマリー

| 項目 | 結果 |
|------|------|
| 総ステップ数 | {total} |
| 成功 | {passed} |
| 失敗 | {failed} |
| スキップ | {skipped} |

## Part 1: 未認証アクセス制御

### Step 1-1: 管理画面URLにアクセス
- **状態**: ✅ 成功
- **所要時間**: 1.2s

![step-1-1](./part-01_未認証アクセス制御/step-1-1_管理画面URLにアクセス.png)

**検証結果**:
- ✅ URL = /login

---

### Step 1-2: URLバー確認
...
```

## 実装順序

1. **Phase 1: パーサー**
   - `parser.py` - YAMLパーサー
   - `cli/scenario.py` - parse, list コマンド

2. **Phase 2: アクション実行**
   - `actions.py` - 基本アクション (goto, fill, click, select)
   - `assertions.py` - 基本検証 (url, visible, text_contains)

3. **Phase 3: セッション管理**
   - `session.py` - セッション管理
   - 認証状態の保持

4. **Phase 4: ランナー**
   - `runner.py` - ScenarioRunner
   - `cli/scenario.py` - run, step コマンド

5. **Phase 5: レポート**
   - `reporter.py` - レポート生成
   - `cli/scenario.py` - report コマンド
