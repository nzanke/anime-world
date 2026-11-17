# アニメインタビュー検索（サイトの元）

テレビアニメの番組ごとに、関連記事（評論・インタビュー・記事。自分が発表した評論も含む）へのリンクをまとめる静的サイト。
`main` に変更を入れると GitHub Actions が `build.py` を動かし、GitHub Pages に公開する（初回だけ Settings → Pages → Source を「GitHub Actions」にする）。


アニメのインタビュー・レビュー記事を、番組名・スタッフ名・題名で検索できる索引。ページは記事検索（index.html）・スタッフランキング（ranking.html）・このサイトについて・記事リンクの追加（add.html、メニュー外）。
クレジット表（メニューの「クレジット表」）：シーズン別スタッフ表（staff_season.html）・各話クレジット（episode_credits.html）・アニメ映画スタッフ表（film_staff.html）。データは `data/credits/`（1年1ファイル、ページは選んだ年だけ読み込む）で、非公開の anime-database の `tools/hyoron/export_credits.py` で書き出す。

## 制作決定ニュース
制作決定（news.html）と放送・公開前のアニメ（upcoming.html）。データは `data/news.json`（非公開の anime-database の `articles/news_tag.py` が毎日書き出して送る）、表示は `static/news.js`。

## 記事のもと
- `data/articles.json` … 自動で集めた記事の索引（本文なし）。非公開の anime-database の `articles/`（collect.py・tag.py）で作り、毎日 GitHub Actions で更新される
- `content/links.csv` … 手で足した記事（追加ページから）。索引に合わせて表示される
- `data/works.tsv` ほか … 番組・スタッフの基礎データ（ランキングとタグの番組名に使う）

## 手元で確かめる
`python3 build.py` → `_site/index.html`（検索は `python3 -m http.server` などで開く）

## アニメ配信カレンダー（haishin.html）
契約している配信サービスと見る作品を選ぶと、各話をいちばん早く見られる日時で自分用の番組表を作るページ。Googleカレンダーで購読もできる（`haishin/my.ics`）。
- 予定の取得：`.github/workflows/haishin.yml` が毎日2回、`tools/haishin/fetch.py`（取得）→ `build_schedule.py`（作品ごとの配信日時の一覧）を動かし、`data/haishin/schedule.json` を更新する
- 取り先：dアニメストア（今期一覧の裏のAPI）・U-NEXT（今期アニメ一覧ページ）・DMM TV（配信カレンダーの裏のGraphQL）・gamebiz の「放送・配信情報一覧」記事（Netflix・Prime Video ほか。記事のURLは `tools/haishin/sources.json`、季節ごとに足す）・しょぼいカレンダー（地上波キー局・TOKYO MX）
- 購読の設定：`content/haishin_my.json`（ページの「購読の設定に保存」で中身がコピーされ、GitHub の編集画面が開く）。`build.py` が `make_ics.py` で `haishin/my.ics` を書き出す
