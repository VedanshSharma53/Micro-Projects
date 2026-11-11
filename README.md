# MLRIT Micro Projects: AI-Powered Project Repository and Originality Portal

Team MP_TG10, Dept. of CSE, MLR Institute of Technology. Guide: Dr. D.B.K. Kamesh.

Students sign in with their college Google account. They can then:

- check whether a project idea already exists (Sentence-BERT similarity against past projects)
- check their report for plagiarism through the college's iThenticate licence

Faculty review the results and approve or reject proposals. Every report has a code that anyone can verify.

| Folder | Contents |
|---|---|
| `portal/` | Flask app, similarity engine, iThenticate client, evaluation and figures (see [portal/README.md](portal/README.md)) |
| `paper/` | IEEE paper and review deck, plus the scripts that build them |
| root `*.html` | the original static Micro Projects site |

## Run the demo locally

```bash
pip install -r portal/requirements.txt
python -m portal.demo
```

Open http://127.0.0.1:5000 and use the **Demo student** / **Demo faculty** buttons.

## Deploy a public demo

The repository includes a `Dockerfile` and a Render blueprint (`render.yaml`):

1. In the Render dashboard, choose **New → Blueprint** and select this repository.
2. Render builds the image and gives you a `https://<name>.onrender.com` link.

The free plan sleeps when idle; the first visit after that takes about a minute.

Document checks show simulated scores until `ITHENTICATE_URL` and `ITHENTICATE_API_KEY` are set on the host.
