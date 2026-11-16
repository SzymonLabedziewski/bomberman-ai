extends Control
## Menu główne (UI budowane w kodzie).

const FALLBACK_BOTS := ["random", "randomsafe", "planner", "montecarlo", "qlearner"]
const FALLBACK_LABELS := {
	"human": "Człowiek", "random": "Random", "randomsafe": "RandomSafe", "planner": "Planner",
	"montecarlo": "MonteCarlo", "qlearner": "Q-Learning (AI)",
}

var status_label: Label
var server_label: Label
var start_button: Button
var p1_option: OptionButton
var p2_option: OptionButton
var seed_box: SpinBox
var tps_box: SpinBox
var physics_checks := {}
var replay_list: ItemList
var file_dialog: FileDialog
var _choices: Array = []


func _ready() -> void:
	_build_ui()
	Net.connected.connect(_on_connected)
	Net.disconnected.connect(_update_server)
	Net.message.connect(_on_message)
	if Net.is_open():
		_on_connected(Net.hello)
	else:
		_update_server()
	if AppState.cli_replay != "":
		_open_replay(AppState.cli_replay)
	elif AppState.cli_results:
		AppState.cli_results = false
		get_tree().change_scene_to_file.call_deferred("res://scenes/Results.tscn")
	elif AppState.cli_live:
		_wait_and_start_live.call_deferred()


func _wait_and_start_live() -> void:
	while not Net.is_open():
		await get_tree().create_timer(0.2).timeout
	_start_live_with(AppState.live)


func _on_connected(_hello: Dictionary) -> void:
	_fill_bots()
	_update_server()
	Net.send({"type": "list_replays"})


func _update_server() -> void:
	var online := Net.is_open()
	server_label.text = "Serwer: połączono (ws://127.0.0.1:8765)" if online else \
			"Serwer: brak połączenia. Uruchom: python -m bomberman serve"
	server_label.add_theme_color_override("font_color", Color(0.5, 0.9, 0.5) if online else Color(1.0, 0.7, 0.4))
	start_button.disabled = not online


func _on_message(msg: Dictionary) -> void:
	match msg.get("type", ""):
		"replays":
			replay_list.clear()
			for item in msg["items"]:
				replay_list.add_item(item)
		"replay":
			AppState.set_replay(msg["data"])
			get_tree().change_scene_to_file.call_deferred("res://scenes/Game.tscn")
		"error":
			status_label.text = "Błąd serwera: %s" % msg.get("message", "")


func _fill_bots() -> void:
	var bots: Array = Net.hello.get("bots", FALLBACK_BOTS)
	_choices = ["human"] + bots
	var labels: Dictionary = Net.hello.get("labels", FALLBACK_LABELS)
	for option: OptionButton in [p1_option, p2_option]:
		var previous := option.selected
		option.clear()
		for bot in _choices:
			option.add_item(labels.get(bot, bot))
		option.select(clampi(previous, 0, _choices.size() - 1))
	p1_option.select(maxi(0, _choices.find(AppState.live.get("p1", "human"))))
	p2_option.select(maxi(0, _choices.find(AppState.live.get("p2", "planner"))))


func _on_start() -> void:
	var physics := {}
	for key in physics_checks:
		physics[key] = physics_checks[key].button_pressed
	_start_live_with({
		"p1": _choices[p1_option.selected], "p2": _choices[p2_option.selected],
		"seed": int(seed_box.value), "tps": tps_box.value, "physics": physics,
	})


func _start_live_with(settings: Dictionary) -> void:
	AppState.start_live(settings)
	get_tree().change_scene_to_file.call_deferred("res://scenes/Game.tscn")


func _on_mock_replay() -> void:
	_open_replay(AppState.MOCK_REPLAY)


func _on_open_file() -> void:
	var replays := ProjectSettings.globalize_path("res://").path_join("../results/replays").simplify_path()
	if DirAccess.dir_exists_absolute(replays):
		file_dialog.current_dir = replays
	file_dialog.popup_centered(Vector2i(900, 600))


func _open_replay(path: String) -> void:
	var error := AppState.load_replay_file(path)
	if error != "":
		status_label.text = error
		return
	get_tree().change_scene_to_file.call_deferred("res://scenes/Game.tscn")


func _open_results() -> void:
	get_tree().change_scene_to_file("res://scenes/Results.tscn")


func _on_server_replay(index: int) -> void:
	Net.send({"type": "get_replay", "name": replay_list.get_item_text(index)})


func _build_ui() -> void:
	var ui_theme := Theme.new()
	ui_theme.default_font_size = 19
	theme = ui_theme

	var background := ColorRect.new()
	background.color = Color("1d2026")
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(background)

	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	var outer := VBoxContainer.new()
	outer.add_theme_constant_override("separation", 14)
	center.add_child(outer)

	var title := Label.new()
	title.text = "Bomberman AI"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.add_theme_font_size_override("font_size", 52)
	outer.add_child(title)
	var subtitle := Label.new()
	subtitle.text = "Planner (BFS w czasie), Monte Carlo i Q-Learning (AI) na siatce z fizyką"
	subtitle.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	subtitle.add_theme_color_override("font_color", Color(0.75, 0.75, 0.8))
	outer.add_child(subtitle)

	var columns := HBoxContainer.new()
	columns.add_theme_constant_override("separation", 40)
	outer.add_child(columns)
	var left := _column(columns)
	var right := _column(columns)

	_heading("Gra na żywo", left)
	server_label = Label.new()
	server_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	left.add_child(server_label)
	p1_option = _labeled_option("Gracz A (niebieski)", left)
	p2_option = _labeled_option("Gracz B (czerwony)", left)
	var numbers := HBoxContainer.new()
	numbers.add_theme_constant_override("separation", 12)
	left.add_child(numbers)
	seed_box = _spin("Ziarno planszy", 0, 99999, int(AppState.live.get("seed", 1)), numbers)
	tps_box = _spin("Ticki/s", 1, 30, float(AppState.live.get("tps", 6.0)), numbers)
	var physics_label := Label.new()
	physics_label.text = "Fizyka:"
	left.add_child(physics_label)
	var physics_row := HBoxContainer.new()
	left.add_child(physics_row)
	var current: Dictionary = AppState.live.get("physics", {})
	for item in [["kick", "kopanie bomb"], ["knockback", "odrzut"], ["moving_obstacles", "ruchome przeszkody"]]:
		var check := CheckBox.new()
		check.text = item[1]
		check.button_pressed = current.get(item[0], false)
		physics_row.add_child(check)
		physics_checks[item[0]] = check
	start_button = _button("Start", _on_start, left)
	var keys := Label.new()
	keys.text = "Człowiek: strzałki lub WSAD, bomba: spacja.\nDwóch ludzi: A = WSAD + spacja, B = strzałki + Enter."
	keys.add_theme_font_size_override("font_size", 15)
	keys.add_theme_color_override("font_color", Color(0.75, 0.75, 0.8))
	left.add_child(keys)

	_heading("Powtórki", right)
	_button("Odtwórz przykładową powtórkę", _on_mock_replay, right)
	_button("Otwórz plik powtórki...", _on_open_file, right)
	var list_label := Label.new()
	list_label.text = "Powtórki na serwerze (results/replays):"
	right.add_child(list_label)
	replay_list = ItemList.new()
	replay_list.custom_minimum_size = Vector2(0, 220)
	replay_list.item_clicked.connect(func(index: int, _pos: Vector2, _button_index: int) -> void: _on_server_replay(index))
	right.add_child(replay_list)
	_button("Wyniki eksperymentów i turniej", _open_results, right)
	_button("Wyjście", func() -> void: get_tree().quit(), right)

	status_label = Label.new()
	status_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	status_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	status_label.add_theme_color_override("font_color", Color(1.0, 0.6, 0.5))
	outer.add_child(status_label)

	file_dialog = FileDialog.new()
	file_dialog.title = "Wybierz plik powtórki"
	file_dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	file_dialog.access = FileDialog.ACCESS_FILESYSTEM
	file_dialog.filters = PackedStringArray(["*.json ; Powtórki (JSON)"])
	file_dialog.file_selected.connect(_open_replay)
	add_child(file_dialog)
	_fill_bots()


func _column(parent: Control) -> VBoxContainer:
	var box := VBoxContainer.new()
	box.custom_minimum_size = Vector2(470, 0)
	box.add_theme_constant_override("separation", 10)
	parent.add_child(box)
	return box


func _heading(text: String, parent: Control) -> void:
	parent.add_child(HSeparator.new())
	var label := Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", 26)
	parent.add_child(label)


func _labeled_option(text: String, parent: Control) -> OptionButton:
	var row := HBoxContainer.new()
	parent.add_child(row)
	var label := Label.new()
	label.text = text
	label.custom_minimum_size = Vector2(200, 0)
	row.add_child(label)
	var option := OptionButton.new()
	option.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(option)
	return option


func _spin(text: String, low: float, high: float, value: float, parent: Control) -> SpinBox:
	var label := Label.new()
	label.text = text
	parent.add_child(label)
	var box := SpinBox.new()
	box.min_value = low
	box.max_value = high
	box.value = value
	parent.add_child(box)
	return box


func _button(text: String, callback: Callable, parent: Control) -> Button:
	var b := Button.new()
	b.text = text
	b.custom_minimum_size = Vector2(0, 44)
	b.pressed.connect(callback)
	parent.add_child(b)
	return b
