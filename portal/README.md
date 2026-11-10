# Project Originality Portal (prototype)

Flask prototype of the AI-powered project repository: Google sign-in, student self-check, faculty review and verifiable reports.

## Run locally

```bash
pip install -r portal/requirements.txt
```

Demo mode (no Google account needed, "Demo student" / "Demo faculty" buttons on the login page):

```bash
DEV_LOGIN=1 SECRET_KEY=change-me python -m portal.app
```

Open http://127.0.0.1:5000. On first start, the 96 seed projects in `portal/data/seed.py` are embedded into `portal/instance/portal.db`.

## Real Google sign-in

1. In Google Cloud Console, create an OAuth client (type "Web application").
2. Add `http://127.0.0.1:5000/auth/callback` as an authorised redirect URI.
3. Run:

```bash
GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=... ALLOWED_DOMAIN=mlrit.ac.in FACULTY_EMAILS=guide@mlrit.ac.in SECRET_KEY=change-me python -m portal.app
```

Only verified accounts whose `hd` claim is `ALLOWED_DOMAIN` are let in.

## iThenticate document check

Students upload a report on **Check document**. The server sends it to the college's iThenticate licence through the iThenticate v2 API (Turnitin Core API) and shows the similarity %.

Ask the college's iThenticate administrator for:
- the tenant URL
- an API key (a test key first)

Then add these environment variables:

```bash
ITHENTICATE_URL=https://<tenant>.turnitin.com ITHENTICATE_API_KEY=... DOC_CHECKS_PER_WEEK=3
```

- The key never leaves the server.
- Draft checks use `add_to_index: false`.
- The portal stores only the file's SHA-256 fingerprint and the score.

Without a key the page runs in **demo mode**: scores are simulated and labelled as such.

To test the client against a local mock of the API:

```bash
python -m portal.tests.test_ithenticate
```

## Paper results and figures

```bash
python -m portal.evaluate
python -m portal.figures
python paper/build_paper.py
python paper/build_ppt.py
```

`build_ppt.py` updates the review deck. It reads `paper/MP_TG10_Review_PPT_original.pptx` and writes `paper/MP_TG10_Review_PPT_Updated.pptx`, keeping the original template.

`evaluate.py` compares TF-IDF and SBERT on the seed benchmark and writes `portal/eval/results.json`. `figures.py` draws the diagrams and charts. `build_paper.py` writes `paper/GRP10_IEEE_Paper_Revised.docx`.

The seed data is a curated benchmark, not official college records. Replace it with real past-project records from the department and re-run the evaluation before using the numbers as institutional results.
