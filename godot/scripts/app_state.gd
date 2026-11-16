extends Node
## Autoload "AppState": ustawienia z menu i dane przekazywane między scenami.
## Argumenty wiersza poleceń: docs/jak_dziala.md

const MOCK_REPLAY := "res://mock/replay.json"
const SUMMARY_FILE := "../results/summary.json"

var mode := "replay"
var replay: Dictionary = {}
var live := {
	"p1": "human", "p2": "planner", "seed": 1, "tps": 6.0,
	"physics": {"kick": false, "knockback": false, "moving_obstacles": false},
}

var cli_replay := ""
var cli_live := false
var cli_tps := 0.0
var cli_results := false
var cli_tournament: PackedStringArray = []
var results_file := ""
var autoquit := false


func _ready() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--replay="):
			cli_replay = arg.trim_prefix("--replay=")
		elif arg.begins_with("--live="):
			var names := arg.trim_prefix("--live=").split(",")
			if names.size() == 2:
				live["p1"] = names[0]
				live["p2"] = names[1]
				cli_live = true
		elif arg == "--physics":
			live["physics"] = {"kick": true, "knockback": true, "moving_obstacles": true}
		elif arg.begins_with("--tps="):
			cli_tps = float(arg.trim_prefix("--tps="))
			live["tps"] = cli_tps
		elif arg == "--autoquit":
			autoquit = true
		elif arg == "--results" or arg.begins_with("--results="):
			cli_results = true
			results_file = arg.trim_prefix("--results").trim_prefix("=")
		elif arg.begins_with("--tournament="):
			cli_tournament = arg.trim_prefix("--tournament=").split(",")
			cli_results = true


## Ścieżka do summary.json z eksperymentów (względem folderu projektu Godota).
func summary_path() -> String:
	var path := results_file if results_file != "" else SUMMARY_FILE
	if path.begins_with("res://") or path.begins_with("user://") or path.is_absolute_path():
		return path
	return ProjectSettings.globalize_path("res://").path_join(path).simplify_path()


## Wczytuje powtórkę z pliku JSON. Zwraca pusty tekst albo opis błędu.
func load_replay_file(path: String) -> String:
	if not FileAccess.file_exists(path):
		return "Nie ma pliku: %s" % path
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if typeof(data) != TYPE_DICTIONARY or not data.has("frames") or data["frames"].is_empty():
		return "To nie jest plik powtórki: %s" % path
	set_replay(data)
	return ""


func set_replay(data: Dictionary) -> void:
	replay = data
	mode = "replay"


func start_live(settings: Dictionary) -> void:
	live = settings
	mode = "live"
