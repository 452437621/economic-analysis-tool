"""Facade modules must keep the pre-split public names and object identity."""

from __future__ import annotations

import pytest

import app.lens.engine as engine
import app.lens.fed as fed
import app.lens.fed_catalog as fed_catalog
import app.lens.fed_readings as fed_readings
import app.lens.fed_state as fed_state
import app.lens.layers as layers
import app.lens.layers_catalog as layers_catalog
import app.lens.layers_frame as layers_frame
import app.lens.layers_macro as layers_macro
import app.lens.layers_micro as layers_micro
import app.lens.persona as persona
import app.lens.persona_engine as persona_engine
import app.lens.persona_expression as persona_expression
import app.lens.persona_spec as persona_spec
import app.lens.song as song
import app.lens.song_catalog as song_catalog
import app.lens.song_readings as song_readings
import app.lens.song_state as song_state
import app.lens.state as state
import app.lens.synthesis as synthesis
from app.lens import config as lens_config
from app.lens import helpers as lens_helpers

pytestmark = pytest.mark.unit


IDENTITIES = [
    (fed, fed_state, "build_fed"),
    (fed, fed_readings, "build_readings"),
    (fed, fed_state, "build_state"),
    (fed, fed_catalog, "CATALOG"),
    (fed, fed_catalog, "_reading"),
    (fed, fed_catalog, "_missing"),
    (fed, fed_readings, "_composite"),
    (fed, fed_state, "_asset_scores"),
    (song, song_state, "build_song"),
    (song, song_readings, "build_readings"),
    (song, song_state, "build_state"),
    (song, song_catalog, "CATALOG"),
    (song, song_catalog, "_reading"),
    (song, song_catalog, "_missing"),
    (song, song_readings, "_yoy_pct"),
    (song, song_state, "_heart"),
    (layers, layers_frame, "build_frame"),
    (layers, layers_macro, "build_macro_layer"),
    (layers, layers_micro, "build_micro_layer"),
    (layers, layers_catalog, "MACRO_READINGS"),
    (layers, layers_catalog, "MICRO_READINGS"),
    (layers, layers_frame, "_metric"),
    (layers, layers_frame, "_direction"),
    (layers, layers_macro, "_REGIMES"),
    (persona, persona_engine, "build_personas"),
    (persona, persona_engine, "build_persona"),
    (persona, persona_engine, "build_readings"),
    (persona, persona_engine, "build_scores"),
    (persona, persona_engine, "build_state"),
    (persona, persona_spec, "load_specs"),
    (persona, persona_spec, "validate_spec"),
    (persona, persona_spec, "PersonaSpec"),
    (persona, persona_spec, "TAIL_ROWS"),
    (persona, persona_spec, "ASSET_IDS"),
    (persona, persona_spec, "_load_spec"),
    (persona, persona_spec, "_cache"),
    (persona, persona_expression, "evaluate_expression"),
    (persona, persona_expression, "normalize_expression"),
    (persona, persona_expression, "ExpressionError"),
    (persona, persona_expression, "_pct"),
    (persona, persona_expression, "_sum12"),
    (engine, lens_config, "load_config"),
    (engine, lens_config, "CONFIG_PATH"),
    (engine, lens_config, "_load_config_cached"),
    (engine, lens_helpers, "ASSETS"),
    (engine, lens_helpers, "GOLD_COLUMNS"),
    (engine, lens_helpers, "METHOD_ENGINE"),
    (engine, lens_helpers, "METHOD_FED"),
    (engine, lens_helpers, "METHOD_SONG"),
    (engine, lens_helpers, "METHOD_SYNTHESIS"),
    (engine, lens_helpers, "METHOD_MACRO"),
    (engine, lens_helpers, "METHOD_MICRO"),
    (engine, lens_helpers, "METHOD_PERSONA"),
    (engine, lens_helpers, "_evaluate_rules"),
    (engine, lens_helpers, "_lens_scores"),
    (engine, lens_helpers, "_warning_list"),
    (engine, lens_helpers, "_observation_rows"),
    (engine, synthesis, "_synthesis"),
    (engine, synthesis, "_outlook"),
    (engine, state, "latest_state"),
    (engine, state, "latest_forecasts"),
    (engine, state, "create_forecast"),
    (engine, state, "forecast_payload"),
    (engine, state, "_latest_derivation"),
]


def test_reexported_objects_are_identical():
    for facade, implementation, name in IDENTITIES:
        assert getattr(facade, name) is getattr(implementation, name), f"{facade.__name__}.{name}"


PUBLIC_NAMES = {
    "app.lens.fed": {"CATALOG", "build_fed", "build_readings", "build_state"},
    "app.lens.song": {"CATALOG", "build_song", "build_readings", "build_state"},
    "app.lens.layers": {
        "MACRO_READINGS",
        "MICRO_READINGS",
        "build_frame",
        "build_macro_layer",
        "build_micro_layer",
    },
    "app.lens.persona": {
        "ASSET_IDS",
        "ExpressionError",
        "PersonaSpec",
        "TAIL_ROWS",
        "build_persona",
        "build_personas",
        "evaluate_expression",
        "load_specs",
        "normalize_expression",
        "validate_spec",
    },
    "app.lens.engine": {
        "ASSETS",
        "GOLD_COLUMNS",
        "METHOD_ENGINE",
        "METHOD_FED",
        "METHOD_MACRO",
        "METHOD_MICRO",
        "METHOD_PERSONA",
        "METHOD_SONG",
        "METHOD_SYNTHESIS",
        "create_forecast",
        "forecast_payload",
        "latest_forecasts",
        "latest_state",
        "load_config",
        "run_lenses",
    },
}


def test_facades_export_required_names():
    import importlib

    for module_name, names in PUBLIC_NAMES.items():
        module = importlib.import_module(module_name)
        assert names <= set(module.__all__), module_name
        for name in names:
            assert hasattr(module, name), f"{module_name}.{name}"


def test_run_lenses_is_defined_in_engine():
    assert engine.run_lenses.__module__ == "app.lens.engine"
    assert "run_lenses" in engine.__all__
