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
