import json, sys, random
out = sys.argv[1]; r = random.Random(3)
users = [{"id": i, "name": f"User {i}", "email": f"user{i}@example.com", "active": r.random() > .3,
          "address": {"city": r.choice(["Dhaka","Khulna","Sylhet"]), "zip": str(1000+i)}, "tags": r.sample(["a","b","c","d"], 2),
          "notes": None if i % 2 else ""} for i in range(1, 41)]
json.dump({"count": 40, "users": users, "meta": {"generated": "2026-10-24", "source": "demo"}}, open(f"{out}/users.json", "w"), indent=2)
json.dump(users[:3], open(f"{out}/small.json", "w"))
open(f"{out}/events.jsonl", "w").write("\n".join(json.dumps({"ts": f"2026-10-24T10:0{i}:00Z", "level": "info", "msg": f"job {i} done"}) for i in range(6)))
open(f"{out}/config.yaml", "w").write("server:\n  host: 0.0.0.0\n  port: 8080\n  tls: false\nfeatures:\n  - search\n  - export\ndatabase:\n  url: postgres://db/app\n  pool: {min: 2, max: 10}\n")
open(f"{out}/app.toml", "w").write('[tool]\nname = "demo"\nversion = "1.2.0"\n[tool.deps]\nrequests = ">=2"\n')
open(f"{out}/data.xml", "w").write('<?xml version="1.0"?><library><book id="1" lang="en"><title>Dune</title><year>1965</year></book><book id="2" lang="en"><title>Emma</title><year>1815</year></book></library>')
json.dump({"cells": [{"cell_type": "markdown", "source": ["# Analysis\n", "Quick look"]}, {"cell_type": "code", "source": ["import pandas as pd\n", "df.head()"], "outputs": [{"output_type": "execute_result", "data": {"text/plain": ["   a  b\n", "0  1  2"], "image/png": "AAAA"}}]}], "metadata": {"language_info": {"name": "python"}}, "nbformat": 4}, open(f"{out}/nb.ipynb", "w"))
open(f"{out}/page.html", "w").write("""<html><head><title>Release notes</title><style>.x{color:red}</style><script>var a=1;</script></head>
<body><nav><a href="/">Home</a><a href="/docs">Docs</a></nav><main><h1>Release 2.0</h1><p>This release adds <strong>export</strong> and fixes <a href="https://x.test/bug">three bugs</a>.</p>
<ul><li>Faster search<ul><li>indexing</li></ul></li><li>New <code>--compact</code> flag</li></ul>
<table><tr><th>Item</th><th>Status</th></tr><tr><td>Export</td><td>done</td></tr><tr><td>Sync</td><td>planned</td></tr></table>
<pre>pip install demo</pre><img src="a.png" alt="diagram"></main><footer>Copyright 2026</footer></body></html>""")
open(f"{out}/hello.py", "w").write("def hi():\n    return 'x'\n")
open(f"{out}/sheet.gsheet", "w").write('{"url": "https://docs.google.com/spreadsheets/d/abc", "doc_id": "abc"}')
