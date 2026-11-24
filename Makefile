PYTHONPATH=src

.PHONY: test eval eval-api probe cache demo ui report slides all clean external-eval external-check

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
	@if [ -x .venv/bin/streamlit ]; then \
		PYTHONPATH=src .venv/bin/streamlit run app/streamlit_app.py --server.port 8502; \
	else \
		PYTHONPATH=src python3 -m streamlit run app/streamlit_app.py --server.port 8502; \
	fi

report:
	.venv/bin/python report/make_figures.py
	.venv/bin/python report/md_to_pdf.py

slides:
	.venv/bin/python report/build_slides.py

all: test eval probe cache demo
	PYTHONPATH=$(PYTHONPATH) python3 eval/make_report.py

external-eval:
	python3 external/dlawbench/run.py --n-cases 30 --bootstrap 5000

external-check:
	python3 external/dlawbench/verify.py
	python3 -m unittest discover -s external/dlawbench/tests -v

clean:
	rm -rf runs/*.sqlite runs/*.sqlite-wal runs/*.sqlite-shm
