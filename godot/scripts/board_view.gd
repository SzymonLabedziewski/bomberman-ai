extends Node2D
## Rysuje planszę z wiadomości `state` (docs/protokol.md).

const FLOOR_A := Color("4c8c4a")
const FLOOR_B := Color("468446")
const WALL := Color("4f535e")
const WALL_TOP := Color("6b7080")
const BOX := Color("b07a3b")
const BOX_EDGE := Color("70491f")
const FLAME := Color(1.0, 0.5, 0.1, 0.92)
const FLAME_CORE := Color(1.0, 0.92, 0.35, 0.95)
const BOMB := Color("1c1c22")
const BOMB_SHINE := Color(1, 1, 1, 0.35)
const OBSTACLE := Color("8e44ad")
const OBSTACLE_EDGE := Color("5b2c6f")
const PLAYER_COLORS := [Color("4ea8ff"), Color("ff5d73")]

var state: Dictionary = {}
var prev: Dictionary = {}
var cell := 64.0
var show_danger := true
var show_plans := true
var alpha := 1.0:
	set(value):
		alpha = value
		queue_redraw()

var _font: Font
var _tween: Tween


func _ready() -> void:
	_font = ThemeDB.fallback_font


## Pokazuje nowy stan; przy `duration` > 0 z animacją przejścia.
func set_state(new_state: Dictionary, duration: float) -> void:
	prev = state if duration > 0.0 else {}
	state = new_state
	if _tween != null and _tween.is_valid():
		_tween.kill()
	if duration > 0.0 and not prev.is_empty():
		alpha = 0.0
		_tween = create_tween()
		_tween.tween_property(self, "alpha", 1.0, duration)
		_spawn_effects(new_state.get("events", []))
	else:
		alpha = 1.0
	queue_redraw()


func _spawn_effects(events: Array) -> void:
	for e in events:
		var pos := cell_center(Vector2(float(e.get("x", 0)), float(e.get("y", 0))))
		match e.get("type", ""):
			"explosion":
				_burst(pos, FLAME, 48, cell * 4.0, Vector2.ZERO, 180.0, 0.6)
				for d in e.get("open", []):
					var dir := Vector2(float(d[0]), float(d[1]))
					_burst(pos + dir * cell * float(e.get("radius", 2)), FLAME_CORE, 10, cell * 2.0, dir, 35.0, 0.45)
			"kick", "push":
				_burst(pos, Color(0.9, 0.9, 0.85, 0.9), 14, cell * 2.0, Vector2.ZERO, 180.0, 0.35)
			"knock":
				var v := Vector2(float(e.get("vx", 0.0)), float(e.get("vy", 0.0)))
				_burst(pos, Color(1.0, 0.95, 0.4), 18, cell * 3.0, -v.normalized(), 40.0, 0.4)
			"collision":
				_burst(pos, Color(1, 1, 1, 0.9), 10, cell * 2.5, Vector2.ZERO, 180.0, 0.25)


func _burst(pos: Vector2, color: Color, amount: int, speed: float, direction: Vector2, spread: float,
		lifetime: float) -> void:
	var p := CPUParticles2D.new()
	p.position = pos
	p.one_shot = true
	p.amount = amount
	p.lifetime = lifetime
	p.explosiveness = 0.9
	p.direction = direction if direction != Vector2.ZERO else Vector2.RIGHT
	p.spread = spread
	p.gravity = Vector2.ZERO
	p.initial_velocity_min = speed * 0.35
	p.initial_velocity_max = speed
	p.damping_min = speed * 1.2
	p.damping_max = speed * 1.8
	p.scale_amount_min = cell * 0.08
	p.scale_amount_max = cell * 0.2
	var ramp := Gradient.new()
	ramp.set_color(0, color)
	ramp.set_color(1, Color(color, 0.0))
	p.color_ramp = ramp
	p.finished.connect(p.queue_free)
	add_child(p)
	p.emitting = true


func board_size() -> Vector2i:
	if state.is_empty():
		return Vector2i(9, 9)
	return Vector2i(int(state["width"]), int(state["height"]))


func set_overlay(overlay: String, enabled: bool) -> void:
	if overlay == "danger":
		show_danger = enabled
	elif overlay == "plans":
		show_plans = enabled
	queue_redraw()


func cell_center(pos: Vector2) -> Vector2:
	return (pos + Vector2(0.5, 0.5)) * cell


func _draw() -> void:
	if state.is_empty():
		return
	_draw_grid()
	_draw_flames()
	if show_danger:
		_draw_danger()
	_draw_obstacles()
	_draw_bombs()
	if show_plans:
		_draw_plans()
	_draw_players()
	_draw_bomb_badges()


func _draw_grid() -> void:
	var grid: Array = state["grid"]
	var edge := maxf(2.0, cell * 0.05)
	for y in grid.size():
		var row: String = grid[y]
		for x in row.length():
			var r := Rect2(x * cell, y * cell, cell, cell)
			var ch := row[x]
			if ch == "#":
				draw_rect(r, WALL)
				draw_rect(r.grow(-cell * 0.1), WALL_TOP)
				continue
			draw_rect(r, FLOOR_A if (x + y) % 2 == 0 else FLOOR_B)
			if ch == "+":
				var b := r.grow(-cell * 0.07)
				draw_rect(b, BOX)
				draw_rect(b, BOX_EDGE, false, edge)
				draw_line(b.position, b.end, BOX_EDGE, edge * 0.8)
				draw_line(Vector2(b.end.x, b.position.y), Vector2(b.position.x, b.end.y), BOX_EDGE, edge * 0.8)


func _draw_flames() -> void:
	for f in state["flames"]:
		var r := Rect2(float(f[0]) * cell, float(f[1]) * cell, cell, cell)
		draw_rect(r.grow(-cell * 0.03), FLAME)
		draw_rect(r.grow(-cell * 0.22), FLAME_CORE)


func _draw_danger() -> void:
	var debug: Dictionary = state.get("debug", {})
	var danger: Dictionary = debug.get("danger", {})
	var font_size := int(cell * 0.26)
	for key in danger:
		var parts := String(key).split(",")
		var t := int(danger[key])
		var r := Rect2(int(parts[0]) * cell, int(parts[1]) * cell, cell, cell)
		var urgency := clampf(1.0 - (t - 1) / 6.0, 0.2, 1.0)
		draw_rect(r, Color(0.95, 0.1, 0.1, 0.15 + 0.35 * urgency))
		draw_string(_font, r.position + Vector2(cell * 0.07, cell * 0.3), str(t),
				HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, Color(1, 1, 1, 0.95))


func _draw_obstacles() -> void:
	var old := _by_id(prev.get("obstacles", []))
	var half := cell * 0.42
	for o in state["obstacles"]:
		var c := cell_center(_interpolated(o, old))
		var r := Rect2(c - Vector2(half, half), Vector2(half, half) * 2.0)
		draw_rect(r, OBSTACLE)
		draw_rect(r, OBSTACLE_EDGE, false, maxf(2.0, cell * 0.06))


func _draw_bombs() -> void:
	var old := _by_id(prev.get("bombs", []))
	var font_size := int(cell * 0.3)
	var radius := cell * 0.32
	for b in state["bombs"]:
		var c := cell_center(_interpolated(b, old))
		_draw_trail(c, b, Color(0.95, 0.95, 0.95))
		var timer := int(b["timer"])
		var ring: Color = PLAYER_COLORS[int(b["owner"]) % 2]
		if timer <= 2:
			ring = Color(1.0, 0.25, 0.1)
		draw_circle(c, radius, BOMB)
		draw_circle(c + Vector2(-radius, -radius) * 0.35, radius * 0.22, BOMB_SHINE)
		draw_arc(c, radius, 0.0, TAU, 32, ring, maxf(2.0, cell * 0.05), true)
		draw_string(_font, c + Vector2(-cell * 0.5, font_size * 0.36), str(timer),
				HORIZONTAL_ALIGNMENT_CENTER, cell, font_size, Color.WHITE)


func _draw_plans() -> void:
	var debug: Dictionary = state.get("debug", {})
	var plans: Dictionary = debug.get("plans", {})
	for key in plans:
		var plan: Array = plans[key]
		if plan.size() < 2:
			continue
		var points := PackedVector2Array()
		for p in plan:
			points.append(cell_center(Vector2(float(p[0]), float(p[1]))))
		var color: Color = PLAYER_COLORS[int(key) % 2]
		color.a = 0.85
		draw_polyline(points, color, maxf(3.0, cell * 0.07), true)
		draw_circle(points[points.size() - 1], cell * 0.11, color)


func _draw_players() -> void:
	var old: Array = prev.get("players", [])
	var font_size := int(cell * 0.34)
	var radius := cell * 0.36
	for p in state["players"]:
		var pid := int(p["id"])
		var pos := Vector2(float(p["x"]), float(p["y"]))
		if alpha < 1.0 and pid < old.size():
			var o: Dictionary = old[pid]
			pos = Vector2(float(o["x"]), float(o["y"])).lerp(pos, alpha)
		var c := cell_center(pos)
		var alive: bool = p["alive"]
		var color: Color = PLAYER_COLORS[pid % 2]
		if alive:
			_draw_trail(c, p, color)
		if not alive:
			color = color.darkened(0.55)
			color.a = 0.7
		draw_circle(c, radius, color)
		draw_arc(c, radius, 0.0, TAU, 32, Color(1, 1, 1, 0.9 if alive else 0.4), maxf(2.0, cell * 0.04), true)
		draw_string(_font, c + Vector2(-cell * 0.5, font_size * 0.36), "AB"[pid % 2],
				HORIZONTAL_ALIGNMENT_CENTER, cell, font_size, Color.WHITE)
		if p.get("stunned", false):
			draw_arc(c, radius * 1.25, 0.0, TAU, 24, Color(1.0, 0.9, 0.2), maxf(2.0, cell * 0.05), true)
		if not alive:
			var d := radius * 0.75
			var width := maxf(3.0, cell * 0.08)
			draw_line(c + Vector2(-d, -d), c + Vector2(d, d), Color(0.08, 0.08, 0.08), width)
			draw_line(c + Vector2(d, -d), c + Vector2(-d, d), Color(0.08, 0.08, 0.08), width)


## Znaczek bomby pod graczem.
func _draw_bomb_badges() -> void:
	var font_size := int(cell * 0.2)
	var radius := cell * 0.16
	for b in state["bombs"]:
		var pos := Vector2(float(b["x"]), float(b["y"]))
		for p in state["players"]:
			if not p["alive"] or Vector2(float(p["x"]), float(p["y"])).distance_to(pos) >= 0.5:
				continue
			var c := cell_center(pos) + Vector2(cell, cell) * 0.3
			var ring: Color = PLAYER_COLORS[int(b["owner"]) % 2]
			draw_circle(c, radius, BOMB)
			draw_arc(c, radius, 0.0, TAU, 24, ring, maxf(1.5, cell * 0.03), true)
			draw_string(_font, c + Vector2(-radius, font_size * 0.36), str(int(b["timer"])),
					HORIZONTAL_ALIGNMENT_CENTER, radius * 2.0, font_size, Color.WHITE)
			break


## Smuga za ciałem w ślizgu: długość rośnie z prędkością (pola/tick).
func _draw_trail(c: Vector2, body: Dictionary, color: Color) -> void:
	var v := Vector2(float(body.get("vx", 0.0)), float(body.get("vy", 0.0)))
	if v.length() < 0.01:
		return
	var tail := c - v.normalized() * cell * minf(1.6, 0.35 + v.length() * 0.6)
	var width := cell * 0.28
	for i in 4:
		var t := float(i) / 4.0
		var col := Color(color, 0.35 * (1.0 - t))
		draw_line(c.lerp(tail, t), c.lerp(tail, t + 0.25), col, width * (1.0 - t * 0.7), true)


func _interpolated(item: Dictionary, old_items: Dictionary) -> Vector2:
	var pos := Vector2(float(item["x"]), float(item["y"]))
	var key := int(item["id"])
	if alpha < 1.0 and old_items.has(key):
		var o: Dictionary = old_items[key]
		return Vector2(float(o["x"]), float(o["y"])).lerp(pos, alpha)
	return pos


func _by_id(items: Array) -> Dictionary:
	var result := {}
	for item in items:
		result[int(item["id"])] = item
	return result
