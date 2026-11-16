extends Control
## Ekran wyników: wykresy z results/summary.json (z serwera albo z pliku) i turniej na żywo.

const ChartView := preload("res://scripts/chart_view.gd")
const BOTS := ["random", "randomsafe", "planner", "montecarlo", "qlearner"]

var summary: Dictionary = {}
var source_label: Label
var chart_list: ItemList
var chart_view: Control
var p1_option: OptionButton
var p2_option: OptionButton
var games_box: SpinBox
var physics_check: CheckBox
var tournament_button: Button
var progress: ProgressBar
var tournament_label: Label
var _bots: Array = BOTS
var _running := false


func _ready() -> void:
	_build_ui()
	Net.message.connect(_on_message)
	Net.connected.connect(func(_hello: Dictionary) -> void: _on_connected())
	Net.disconnected.connect(_update_online)
	_update_online()
	if AppState.results_file == "" and Net.is_open():
		_on_connected()
	else:
		_load_local()
	if not AppState.cli_tournament.is_empty():
		_wait_and_start_tournament.call_deferred()


func _on_connected() -> void:
	_fill_bots()
	_update_online()
	if AppState.results_file == "":
		source_label.text = "Pobieranie wyników z serwera..."
		Net.send({"type": "get_results"})


func _update_online() -> void:
	tournament_button.disabled = not Net.is_open() and not _running


func _on_message(msg: Dictionary) -> void:
	match msg.get("type", ""):
		"results":
			var data: Variant = msg.get("summary")
			if typeof(data) == TYPE_DICTIONARY:
				_set_summary(data, "serwer: results/summary.json")
			else:
				_load_local()
		"tournament_progress":
			_show_progress(msg)
		"error":
			tournament_label.text = "Błąd serwera: %s" % msg.get("message", "")


func _load_local() -> void:
	var path := AppState.summary_path()
	if not FileAccess.file_exists(path):
		_set_summary({}, "brak pliku %s. Uruchom: python -m bomberman reproduce" % path)
		return
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if typeof(data) != TYPE_DICTIONARY:
		_set_summary({}, "niepoprawny plik %s" % path)
		return
	_set_summary(data, "plik: %s" % path)


func _set_summary(data: Dictionary, source: String) -> void:
	summary = data
	var generated := String(data.get("generated", ""))
	source_label.text = "Źródło: %s%s" % [source, ("\nWygenerowano: " + generated) if generated != "" else ""]
	chart_list.clear()
	var charts: Array = data.get("charts", [])
	for c in charts:
		chart_list.add_item(String(c.get("title", c.get("id", "?"))))
	if charts.is_empty():
		chart_view.set_chart({})
		return
	var wanted := _cli_chart()
	var index := 0
	for i in charts.size():
		if charts[i].get("id", "") == wanted:
			index = i
	chart_list.select(index)
	_on_chart_selected(index)
	if AppState.autoquit and AppState.cli_tournament.is_empty():
		print("Wyniki: %d wykresów (%s)" % [charts.size(), source])
		get_tree().create_timer(0.5).timeout.connect(get_tree().quit)


func _cli_chart() -> String:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--chart="):
			return arg.trim_prefix("--chart=")
	return ""


func _on_chart_selected(index: int) -> void:
	var charts: Array = summary.get("charts", [])
	if index >= 0 and index < charts.size():
		chart_view.set_chart(charts[index])


func _fill_bots() -> void:
	_bots = Net.hello.get("bots", BOTS)
	var labels: Dictionary = Net.hello.get("labels", {})
	for option: OptionButton in [p1_option, p2_option]:
		var previous := option.selected
		option.clear()
		for bot in _bots:
			option.add_item(String(labels.get(bot, bot)))
		option.select(clampi(previous, 0, _bots.size() - 1))


func _wait_and_start_tournament() -> void:
	while not Net.is_open():
		await get_tree().create_timer(0.2).timeout
	var names := AppState.cli_tournament
	p1_option.select(maxi(0, _bots.find(names[0])))
	p2_option.select(maxi(0, _bots.find(names[1] if names.size() > 1 else "montecarlo")))
	_toggle_tournament()


func _toggle_tournament() -> void:
	if _running:
		Net.send({"type": "control", "cmd": "stop"})
		_running = false
		tournament_button.text = "Start turnieju"
		tournament_label.text += "\n(przerwano)"
		return
	_running = true
	tournament_button.text = "Zatrzymaj"
	progress.value = 0
	tournament_label.text = "Trwa turniej..."
	Net.send({
		"type": "tournament", "p1": _bots[p1_option.selected], "p2": _bots[p2_option.selected],
		"games": int(games_box.value), "seed": 1, "physics": physics_check.button_pressed,
	})


func _show_progress(msg: Dictionary) -> void:
	var stats: Dictionary = msg.get("stats", {})
	var names: Array = stats.get("names", ["A", "B"])
	var wins: Array = stats.get("wins", [0, 0])
	var done := int(msg.get("done", 0))
	var total := int(msg.get("total", 1))
	progress.max_value = total
	progress.value = done
	tournament_label.text = "Gry: %d / %d\n%s: %d wygranych\n%s: %d wygranych\nRemisy: %d\nŚrednio %.1f ticków" % [
		done, total, names[0], int(wins[0]), names[1], int(wins[1]), int(stats.get("draws", 0)),
		float(stats.get("avg_ticks", 0.0))]
	if done >= total:
		_running = false
		tournament_button.text = "Start turnieju"
		_update_online()
		if AppState.autoquit:
			print("Turniej zakończony: %s %d, %s %d, remisy %d" % [
				names[0], int(wins[0]), names[1], int(wins[1]), int(stats.get("draws", 0))])
			get_tree().quit()


func _build_ui() -> void:
	var ui_theme := Theme.new()
	ui_theme.default_font_size = 17
	theme = ui_theme
	var background := ColorRect.new()
	background.color = Color("1d2026")
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(background)

	var root := HBoxContainer.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.add_theme_constant_override("separation", 0)
	add_child(root)

	var side_panel := PanelContainer.new()
	side_panel.custom_minimum_size = Vector2(380, 0)
	root.add_child(side_panel)
	var margin := MarginContainer.new()
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 14)
	side_panel.add_child(margin)
	var side := VBoxContainer.new()
	side.add_theme_constant_override("separation", 8)
	margin.add_child(side)

	var title := Label.new()
	title.text = "Wyniki eksperymentów"
	title.add_theme_font_size_override("font_size", 26)
	side.add_child(title)
	source_label = Label.new()
	source_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	source_label.add_theme_font_size_override("font_size", 13)
	source_label.add_theme_color_override("font_color", Color(0.75, 0.75, 0.8))
	side.add_child(source_label)
	chart_list = ItemList.new()
	chart_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	chart_list.item_selected.connect(_on_chart_selected)
	side.add_child(chart_list)

	side.add_child(HSeparator.new())
	var t_title := Label.new()
	t_title.text = "Turniej na żywo (serwer)"
	t_title.add_theme_font_size_override("font_size", 20)
	side.add_child(t_title)
	p1_option = _option("Bot A", side)
	p2_option = _option("Bot B", side)
	for bot in BOTS:
		p1_option.add_item(bot)
		p2_option.add_item(bot)
	p1_option.select(BOTS.find("planner"))
	p2_option.select(BOTS.find("montecarlo"))
	var row := HBoxContainer.new()
	side.add_child(row)
	var games_label := Label.new()
	games_label.text = "Gier:"
	row.add_child(games_label)
	games_box = SpinBox.new()
	games_box.min_value = 1
	games_box.max_value = 200
	games_box.value = 20
	row.add_child(games_box)
	physics_check = CheckBox.new()
	physics_check.text = "z fizyką"
	row.add_child(physics_check)
	tournament_button = Button.new()
	tournament_button.text = "Start turnieju"
	tournament_button.pressed.connect(_toggle_tournament)
	side.add_child(tournament_button)
	progress = ProgressBar.new()
	side.add_child(progress)
	tournament_label = Label.new()
	tournament_label.text = "Wymaga serwera: python -m bomberman serve"
	tournament_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	side.add_child(tournament_label)
	var back := Button.new()
	back.text = "Menu"
	back.pressed.connect(func() -> void: get_tree().change_scene_to_file("res://scenes/Menu.tscn"))
	side.add_child(back)

	chart_view = ChartView.new()
	chart_view.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	chart_view.size_flags_vertical = Control.SIZE_EXPAND_FILL
	root.add_child(chart_view)


func _option(text: String, parent: Control) -> OptionButton:
	var row := HBoxContainer.new()
	parent.add_child(row)
	var label := Label.new()
	label.text = text
	label.custom_minimum_size = Vector2(60, 0)
	row.add_child(label)
	var option := OptionButton.new()
	option.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(option)
	return option


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE:
		get_tree().change_scene_to_file("res://scenes/Menu.tscn")
