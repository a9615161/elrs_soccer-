# One-line build/test/experiment entry points. See README.md.
VENV    ?= .venv
PY      := $(VENV)/bin/python
CMAKE   := $(VENV)/bin/cmake
NINJA   := $(abspath $(VENV)/bin/ninja)
BUILD   := build
PRP_SLOTS ?= 1000000
export UV_CACHE_DIR ?= /data/richardlin/uv-cache

# EXP short name -> analysis/simulation entry point
EXP_SCRIPT_e1 := analysis/e1_orthogonality.py
EXP_CONFIG_e1 := configs/e1_orthogonality.yaml
EXP_SCRIPT_e1sat := analysis/e1_orthogonality.py
EXP_CONFIG_e1sat := configs/e1_saturation.yaml
EXP_SCRIPT_e2 := analysis/e2_prediction.py
EXP_CONFIG_e2 := configs/e2_prediction.yaml
EXP_SCRIPT_e3 := analysis/e3_forgery.py
EXP_CONFIG_e3 := configs/e3_forgery.yaml

EXP_SCRIPT_e4 := analysis/e4_bit_budget.py
EXP_SCRIPT_e5 := analysis/e5_baseline.py
EXP_SCRIPT_e6 := analysis/e6_drift.py
EXP_CONFIG_e6 := configs/e6_drift.yaml
EXP_SCRIPT_e7 := scripts/run_experiment.py
EXP_CONFIG_e7 := configs/e7_burst.yaml
EXP_SCRIPT_e7blackout := scripts/run_experiment.py
EXP_CONFIG_e7blackout := configs/e7_blackout.yaml
EXP_SCRIPT_e7reboot := scripts/run_experiment.py
EXP_CONFIG_e7reboot := configs/e7_reboot.yaml
EXP_SCRIPT_e8key := scripts/run_experiment.py
EXP_CONFIG_e8key := configs/e8_key.yaml
EXP_SCRIPT_e8syncjam := scripts/run_experiment.py
EXP_CONFIG_e8syncjam := configs/e8_syncjam.yaml
EXP_SCRIPT_e8 := scripts/run_experiment.py
EXP_CONFIG_e8 := configs/e8_jamming.yaml
EXP_SCRIPT_e9 := analysis/e9_multidrone.py
EXP_CONFIG_e9 := configs/e9_multidrone.yaml
EXP_SCRIPT_e10 := scripts/run_experiment.py
EXP_CONFIG_e10 := configs/e10_cost.yaml

.PHONY: setup lib test-c test exp plots clean

$(PY):
	uv venv --python 3.12 $(VENV)
	uv pip install --python $(PY) -r requirements.lock

setup: $(PY)

lib: $(PY)
	$(CMAKE) -S libproto -B $(BUILD) -G Ninja -DCMAKE_MAKE_PROGRAM=$(NINJA)
	$(CMAKE) --build $(BUILD)

test-c: lib
	./$(BUILD)/test_proto $(PRP_SLOTS)

test: lib
	$(PY) -m pytest -q tests

exp: lib
	@test -n "$(EXP_SCRIPT_$(EXP))" || (echo "unknown EXP=$(EXP)"; exit 1)
	$(PY) $(EXP_SCRIPT_$(EXP)) $(if $(EXP_CONFIG_$(EXP)),--config $(EXP_CONFIG_$(EXP))) $(ARGS)

plots:
	$(PY) scripts/plot_$(EXP).py

clean:
	rm -rf $(BUILD)
