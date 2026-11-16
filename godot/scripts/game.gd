extends Control
## Scena gry: powtórka albo gra na żywo.

const BoardView := preload("res://scripts/board_view.gd")
const SPEEDS := [1.0, 2.0, 4.0, 6.0, 10.0, 20.0]
const PLAYER_HEX := ["4ea8ff", "ff5d73"]
const MODE_NAMES := {
	"escape": "ucieczka", "survive": "ratunek (brak ucieczki)", "attack": "atak", "approach": "podchodzenie",
	"yield": "ustępowanie pola", "wait": "czekanie", "stunned": "ogłuszony", "montecarlo": "symulacje",
	"exploit": "Q exploit", "explore": "Q explore", "random": "losowy", "randomsafe": "losowy bezpieczny",
}
const FAMILY_NAMES := {"random": "losowy", "search": "algorytm", "rl": "AI (RL)", "human": "człowiek"}
const KEYS_WSAD := {KEY_W: "UP", KEY_S: "DOWN", KEY_A: "LEFT", KEY_D: "RIGHT"}
const KEYS_ARROWS := {KEY_UP: "UP", KEY_DOWN: "DOWN", KEY_LEFT: "LEFT", KEY_RIGHT: "RIGHT"}

var board: BoardView
var board_area: Control
var title_label: Label
var info_label: RichTextLabel
var pause_button: Button
var speed_label: Label
var slider: HSlider
var help_label: Label

var live := false
var frames: Array = []
var frame_idx := 0
var playing := true
var speed_idx := 3
var humans: Array[int] = []
var _held := ["", ""]
var _accum := 0.0
var _slider_lock := false
var _live_over := false
var _last_compute_totals: Array = []


func _ready() -> void:
	live = AppState.mode == "live"
	var wanted: float = AppState.cli_tps if AppState.cli_tps > 0.0 else float(AppState.live.get("tps", 6.0))
	if live or AppState.cli_tps > 0.0:
		speed_idx = _nearest_speed(wanted)
	_build_ui()
	if live:
		_start_live()
		return
	frames = AppState.replay.get("frames", [])
	if frames.is_empty():
		title_label.text = "Brak powtórki"
		return
	slider.max_value = frames.size() - 1
	_show_frame(0, false)
	_fit_board()
	_update_controls()


func _process(delta: float) -> void:
	if live or not playing or frames.is_empty():
		return
	if frame_idx >= frames.size() - 1:
		playing = false
		_update_controls()
		if AppState.autoquit:
			print("Powtórka zakończona: %d klatek, wynik: %s" % [frames.size(), _result_text(frames[-1]["winner"])])
			get_tree().quit()
		return
	_accum += delta
	var period := 1.0 / tps()
	if _accum >= period:
		_accum -= period
		_show_frame(frame_idx + 1, true)


func tps() -> float:
	return SPEEDS[speed_idx]


func _start_live() -> void:
	var s: Dictionary = AppState.live
	for seat in [0, 1]:
		if s["p%d" % (seat + 1)] == "human":
			humans.append(seat)
	Net.message.connect(_on_net_message)
	Net.disconnected.connect(_on_disconnected)
	var msg := s.duplicate()
	msg["type"] = "start"
	msg["tps"] = tps()
	if not Net.send(msg):
		title_label.text = "Brak połączenia z serwerem"
	help_label.text = _live_help()
	_update_controls()


func _on_net_message(msg: Dictionary) -> void:
	match msg.get("type", ""):
		"state":
			var first: bool = board.state.is_empty()
			board.set_state(msg, 0.0 if first else 0.85 / tps())
			if first:
				var names: Array = []
				for p in msg["players"]:
					names.append(p.get("name", ""))
				title_label.text = "Na żywo: %s vs %s" % names
				_fit_board()
			_update_info(msg)
		"game_over":
			_live_over = true
			playing = false
			var stats: Dictionary = msg.get("stats", {})
			_last_compute_totals = stats.get("compute_totals", [])
			if board.state:
				_update_info(board.state)
			_update_controls()
			if AppState.autoquit:
				print("Gra na żywo zakończona po %d tickach, wynik: %s" % [int(msg["ticks"]), _result_text(msg["winner"])])
				get_tree().quit()
		"error":
			title_label.text = "Błąd: %s" % msg.get("message", "")
			if AppState.autoquit:
				printerr("Błąd serwera: %s" % msg.get("message", ""))
				get_tree().quit(1)


func _on_disconnected() -> void:
	title_label.text = "Utracono połączenie z serwerem"


func _send_input(pid: int, action: String) -> void:
	Net.send({"type": "input", "action": action, "player": pid})


func _human_key(key: InputEventKey) -> bool:
	if humans.is_empty():
		return false
	var code := key.keycode
	var pid := -1
	var action := ""
	if humans.size() == 1:
		pid = humans[0]
		action = KEYS_WSAD.get(code, KEYS_ARROWS.get(code, ""))
		if code in [KEY_SPACE, KEY_ENTER, KEY_KP_ENTER]:
			action = "BOMB"
	else:
		if KEYS_WSAD.has(code) or code == KEY_SPACE:
			pid = 0
			action = "BOMB" if code == KEY_SPACE else KEYS_WSAD[code]
		elif KEYS_ARROWS.has(code) or code in [KEY_ENTER, KEY_KP_ENTER]:
			pid = 1
			action = "BOMB" if code in [KEY_ENTER, KEY_KP_ENTER] else KEYS_ARROWS[code]
	if action == "":
		return false
	if key.echo:
		return true
	if key.pressed:
		if action != "BOMB":
			_held[pid] = action
		_send_input(pid, action)
	elif action != "BOMB" and _held[pid] == action:
		_held[pid] = ""
		_send_input(pid, "STAY")
	return true


func _live_help() -> String:
	var lines := PackedStringArray()
	if humans.size() == 1:
		lines.append("Ty grasz jako %s: strzałki lub WSAD, bomba: spacja" % "AB"[humans[0]])
	elif humans.size() == 2:
		lines.append("A: WSAD + spacja    B: strzałki + Enter")
	lines.append("P: pauza   N: krok   +/-: prędkość   1/2: nakładki   Esc: menu")
	lines.append("Czerwone pola: za ile ticków będzie tam ogień")
	lines.append("Linie: zaplanowane ścieżki Plannera")
	return "\n".join(lines)


func _unhandled_input(event: InputEvent) -> void:
	var key := event as InputEventKey
	if key == null:
		return
	if live and _human_key(key):
		get_viewport().set_input_as_handled()
		return
	if not key.pressed or key.echo:
		return
	match key.keycode:
		KEY_P:
			_toggle_pause()
		KEY_SPACE:
			if humans.is_empty():
				_toggle_pause()
		KEY_N, KEY_PERIOD:
			_step(1)
		KEY_RIGHT:
			if not live:
				_step(1)
		KEY_LEFT, KEY_COMMA:
			if not live:
				_step(-1)
		KEY_EQUAL, KEY_PLUS, KEY_KP_ADD:
			_change_speed(1)
		KEY_MINUS, KEY_KP_SUBTRACT:
			_change_speed(-1)
		KEY_1:
			_toggle_overlay("danger")
		KEY_2:
			_toggle_overlay("plans")
		KEY_ESCAPE:
			_back()


func _toggle_pause() -> void:
	if live:
		if _live_over:
			return
		playing = not playing
		Net.send({"type": "control", "cmd": "resume" if playing else "pause"})
	else:
		if frames.is_empty():
			return
		if not playing and frame_idx >= frames.size() - 1:
			_show_frame(0, false)
		playing = not playing
		_accum = 0.0
	_update_controls()


func _step(delta: int) -> void:
	if live:
		if delta > 0 and not _live_over:
			playing = false
			Net.send({"type": "control", "cmd": "step"})
			_update_controls()
		return
	if frames.is_empty():
		return
	playing = false
	_show_frame(frame_idx + delta, delta > 0)
	_update_controls()


func _change_speed(delta: int) -> void:
	speed_idx = clampi(speed_idx + delta, 0, SPEEDS.size() - 1)
	if live:
		Net.send({"type": "control", "cmd": "speed", "value": tps()})
	_update_controls()


func _toggle_overlay(overlay: String) -> void:
	var enabled := not (board.show_danger if overlay == "danger" else board.show_plans)
	board.set_overlay(overlay, enabled)


func _back() -> void:
	if live:
		Net.send({"type": "control", "cmd": "stop"})
	get_tree().change_scene_to_file("res://scenes/Menu.tscn")


func _nearest_speed(value: float) -> int:
	var best := 0
	for i in SPEEDS.size():
		if absf(SPEEDS[i] - value) < absf(SPEEDS[best] - value):
			best = i
	return best


func _show_frame(i: int, animate: bool) -> void:
	frame_idx = clampi(i, 0, frames.size() - 1)
	var s: Dictionary = frames[frame_idx]
	board.set_state(s, 0.9 / tps() if animate else 0.0)
	_slider_lock = true
	slider.value = frame_idx
	_slider_lock = false
	_update_info(s)


func _on_slider(value: float) -> void:
	if _slider_lock or frames.is_empty():
		return
	playing = false
	_show_frame(int(value), false)
	_update_controls()


func _update_controls() -> void:
	pause_button.text = "Pauza" if playing else "Graj"
	speed_label.text = "%s t/s" % str(tps())


func _update_info(s: Dictionary) -> void:
	var debug: Dictionary = s.get("debug", {})
	var modes: Dictionary = debug.get("modes", {})
	var actions: Dictionary = debug.get("actions", {})
	var values: Dictionary = debug.get("values", {})
	var families: Dictionary = debug.get("families", {})
	var compute: Dictionary = debug.get("compute", {})
	var rationales: Dictionary = debug.get("rationales", {})
	var lines := PackedStringArray()
	if live:
		lines.append("[b]Tick %d[/b]" % int(s["tick"]))
	else:
		lines.append("[b]Tick %d[/b] z %d" % [int(s["tick"]), int(frames[-1]["tick"])])
	lines.append("")
	for p in s["players"]:
		var pid := int(p["id"])
		var key := str(pid)
		var status := "żyje" if p["alive"] else "[color=#999999]nie żyje[/color]"
		if p.get("stunned", false):
			status += ", ogłuszony"
		var family := ""
		if families.has(key):
			family = " [%s]" % FAMILY_NAMES.get(str(families[key]), str(families[key]))
		lines.append("[color=#%s][b]%s[/b][/color] %s%s: %s" % [
			PLAYER_HEX[pid], "AB"[pid], p.get("name", ""), family, status])
		var details := PackedStringArray()
		if actions.has(key):
			details.append("akcja %s" % actions[key])
		if modes.has(key):
			details.append("tryb: %s" % MODE_NAMES.get(modes[key], modes[key]))
		if not details.is_empty():
			lines.append("    " + ", ".join(details))
		if values.has(key):
			var label := "oceny Q" if str(families.get(key, "")) == "rl" else "oceny"
			lines.append("    %s: %s" % [label, _format_values(values[key])])
		if compute.has(key):
			lines.append("    zasoby: " + _format_compute(compute[key]))
		if rationales.has(key):
			lines.append("    -> %s" % str(rationales[key]))
	var bombs: Array = s["bombs"]
	if not bombs.is_empty():
		lines.append("")
		var timers := PackedStringArray()
		for b in bombs:
			var moving := absf(float(b["vx"])) + absf(float(b["vy"])) > 0.0
			timers.append("%s:%d%s" % ["AB"[int(b["owner"]) % 2], int(b["timer"]), " (ślizg)" if moving else ""])
		lines.append("Bomby (właściciel:zapalnik): " + "  ".join(timers))
	if s["done"]:
		lines.append("")
		var winner := int(s["winner"]) if s["winner"] != null else -1
		if winner >= 0:
			var winner_name: String = s["players"][winner].get("name", "")
			lines.append("[b]Wygrywa %s (%s)[/b]" % ["AB"[winner], winner_name])
		else:
			lines.append("[b]Remis[/b]")
		if _last_compute_totals.size() > 0:
			lines.append("")
			lines.append("[b]Koszty decyzji (mecz):[/b]")
			for tot in _last_compute_totals:
				lines.append("  %s [%s]: śr. %.2f ms, ops śr. %.1f, RSS śr. %.0f KiB" % [
					str(tot.get("name", "?")),
					FAMILY_NAMES.get(str(tot.get("family", "")), str(tot.get("family", "?"))),
					float(tot.get("wall_ms_mean", 0.0)),
					float(tot.get("ops_mean", 0.0)),
					float(tot.get("rss_kb_mean", 0.0)),
				])
	info_label.text = "\n".join(lines)


func _format_compute(c: Dictionary) -> String:
	var ms := float(c.get("wall_ms", 0.0))
	var ops := int(c.get("ops", 0))
	var rss := float(c.get("rss_kb", 0.0))
	var detail := str(c.get("detail", ""))
	var text := "%.2f ms | %d ops | RSS %.0f KiB" % [ms, ops, rss]
	if detail != "":
		text += " (%s)" % detail
	return text


static func _result_text(winner: Variant) -> String:
	if winner == null or int(winner) < 0:
		return "remis"
	return "wygrywa " + "AB"[int(winner)]


func _format_values(values: Dictionary) -> String:
	var pairs: Array = []
	for action in values:
		pairs.append([float(values[action]), action])
	pairs.sort()
	pairs.reverse()
	var parts := PackedStringArray()
	for pair in pairs:
		parts.append("%s %+.2f" % [pair[1], pair[0]])
	return "  ".join(parts)


func _build_ui() -> void:
	var ui_theme := Theme.new()
	ui_theme.default_font_size = 18
	theme = ui_theme

	var background := ColorRect.new()
	background.color = Color("1d2026")
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(background)

	var root := HBoxContainer.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(root)

	board_area = Control.new()
	board_area.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	board_area.size_flags_vertical = Control.SIZE_EXPAND_FILL
	board_area.clip_contents = true
	board_area.resized.connect(_fit_board)
	root.add_child(board_area)
	board = BoardView.new()
	board_area.add_child(board)

	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(420, 0)
	root.add_child(panel)
	var margin := MarginContainer.new()
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 16)
	panel.add_child(margin)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 10)
	margin.add_child(box)

	title_label = Label.new()
	title_label.add_theme_font_size_override("font_size", 24)
	title_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	box.add_child(title_label)
	if live:
		title_label.text = "Łączenie z grą..."
	else:
		var meta: Dictionary = AppState.replay.get("meta", {})
		title_label.text = "Powtórka: %s vs %s" % [meta.get("p1", "?"), meta.get("p2", "?")]

	info_label = RichTextLabel.new()
	info_label.bbcode_enabled = true
	info_label.fit_content = true
	info_label.scroll_active = false
	info_label.size_flags_vertical = Control.SIZE_EXPAND_FILL
	box.add_child(info_label)

	slider = HSlider.new()
	slider.min_value = 0
	slider.step = 1
	slider.focus_mode = Control.FOCUS_NONE
	slider.value_changed.connect(_on_slider)
	slider.visible = not live
	box.add_child(slider)

	var controls := HBoxContainer.new()
	controls.add_theme_constant_override("separation", 6)
	box.add_child(controls)
	pause_button = _button("Pauza", _toggle_pause, controls)
	if not live:
		_button("< Krok", func() -> void: _step(-1), controls)
	_button("Krok >", func() -> void: _step(1), controls)
	_button("-", func() -> void: _change_speed(-1), controls)
	speed_label = Label.new()
	controls.add_child(speed_label)
	_button("+", func() -> void: _change_speed(1), controls)

	var overlays := HBoxContainer.new()
	box.add_child(overlays)
	_check("Zagrożenia [1]", board.show_danger, func(on: bool) -> void: board.set_overlay("danger", on), overlays)
	_check("Plany [2]", board.show_plans, func(on: bool) -> void: board.set_overlay("plans", on), overlays)

	help_label = Label.new()
	help_label.text = "Spacja: pauza   strzałki: krok   +/-: prędkość\n1/2: nakładki   Esc: menu\nCzerwone pola: za ile ticków będzie tam ogień\nLinie: zaplanowane ścieżki Plannera"
	help_label.add_theme_color_override("font_color", Color(0.75, 0.75, 0.8))
	help_label.add_theme_font_size_override("font_size", 15)
	box.add_child(help_label)
	_button("Menu", _back, box)


func _button(text: String, callback: Callable, parent: Control) -> Button:
	var b := Button.new()
	b.text = text
	b.focus_mode = Control.FOCUS_NONE
	b.pressed.connect(callback)
	parent.add_child(b)
	return b


func _check(text: String, value: bool, callback: Callable, parent: Control) -> CheckBox:
	var c := CheckBox.new()
	c.text = text
	c.button_pressed = value
	c.focus_mode = Control.FOCUS_NONE
	c.toggled.connect(callback)
	parent.add_child(c)
	return c


func _fit_board() -> void:
	if board == null or board_area == null:
		return
	var dims := Vector2(board.board_size())
	var area := board_area.size
	var cell := floorf(minf((area.x - 32.0) / dims.x, (area.y - 32.0) / dims.y))
	board.cell = maxf(cell, 8.0)
	board.position = ((area - dims * board.cell) / 2.0).floor()
	board.queue_redraw()
