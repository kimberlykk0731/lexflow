PYTHONPATH=src

.PHONY: test eval eval-api probe cache demo ui report slides all clean

test:
	PYTHONPATH=$(PYTHONPATH) python3 -m unittest discover -s tests -v

eval:
	PYTHONPATH=$(PYTHONPATH) python3 eval/run_evals.py --llm mock --out runs/mock

eval-api:
	PYTHONPATH=$(PYTHONPATH) python3 eval/run_evals.py --llm api --out runs/api

probe:
	PYTHONPATH=$(PYTHONPATH) python3 eval/verify_probe.py

cache:
	PYTHONPATH=$(PYTHONPATH) python3 eval/cache_bench.py

demo:
	PYTHONPATH=$(PYTHONPATH) python3 -m lexflow.cli demo --with-tort

ui:
	PYTHONPATH=$(PYTHONPATH) python3 -m streamlit run app/streamlit_app.py --server.port 8502

report:
	.venv/bin/python report/make_figures.py
	.venv/bin/python report/md_to_pdf.py

slides:
	.venv/bin/python report/build_slides.py

all: test eval probe cache demo
	PYTHONPATH=$(PYTHONPATH) python3 eval/make_report.py

clean:
	rm -rf runs/*.sqlite runs/*.sqlite-wal runs/*.sqlite-shm
