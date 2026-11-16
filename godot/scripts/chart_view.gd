extends Control
## Wykres słupkowy z `summary.json` z opcjonalnymi przedziałami ufności.

const COLORS := [Color("4ea8ff"), Color("ffb347"), Color("ff5d73"), Color("7bd88f"), Color("c39bff")]
const AXIS := Color(0.75, 0.75, 0.8)
const GRID := Color(1, 1, 1, 0.08)

var chart: Dictionary = {}
var _font: Font


func _ready() -> void:
	_font = ThemeDB.fallback_font
	resized.connect(queue_redraw)


func set_chart(data: Dictionary) -> void:
	chart = data
	queue_redraw()


func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), Color("23272f"))
	if chart.is_empty():
		_text(size / 2.0 - Vector2(200, 0), "Wybierz wykres z listy", 18, AXIS, 400)
		return
	var labels: Array = chart.get("labels", [])
	var series: Array = chart.get("series", [])
	var percent: bool = chart.get("percent", false)
	_text(Vector2(16, 30), chart.get("title", ""), 20, Color.WHITE, size.x - 32, HORIZONTAL_ALIGNMENT_LEFT)

	var plot := Rect2(70, 90, size.x - 90, size.y - 175)
	var top := 1.0 if percent else 0.0
	for s in series:
		for v in s.get("values", []):
			top = maxf(top, float(v))
		for v in s.get("ci_high", []):
			top = maxf(top, float(v))
	if not percent:
		top = maxf(top * 1.12, 1e-6)

	for i in 6:
		var frac := i / 5.0
		var y := plot.end.y - frac * plot.size.y
		draw_line(Vector2(plot.position.x, y), Vector2(plot.end.x, y), GRID, 1.0)
		var value := frac * top
		var label := "%d%%" % roundi(value * 100.0) if percent else _short(value)
		_text(Vector2(0, y + 5), label, 13, AXIS, plot.position.x - 8, HORIZONTAL_ALIGNMENT_RIGHT)
	draw_line(plot.position + Vector2(0, plot.size.y), plot.end, AXIS, 1.5)
	_text(Vector2(8, plot.position.y - 14), chart.get("ylabel", ""), 13, AXIS, 300, HORIZONTAL_ALIGNMENT_LEFT)

	var n := maxi(1, labels.size())
	var m := maxi(1, series.size())
	var group := plot.size.x / n
	var bar := group * 0.78 / m
	for si in series.size():
		var s: Dictionary = series[si]
		var color: Color = COLORS[si % COLORS.size()]
		var values: Array = s.get("values", [])
		var lows: Array = s.get("ci_low", [])
		var highs: Array = s.get("ci_high", [])
		for gi in values.size():
			var v := float(values[gi])
			var x := plot.position.x + gi * group + group * 0.11 + si * bar
			var h := v / top * plot.size.y
			draw_rect(Rect2(x, plot.end.y - h, bar * 0.92, h), color)
			if gi < lows.size() and gi < highs.size():
				var cx := x + bar * 0.46
				var y_lo := plot.end.y - float(lows[gi]) / top * plot.size.y
				var y_hi := plot.end.y - float(highs[gi]) / top * plot.size.y
				draw_line(Vector2(cx, y_lo), Vector2(cx, y_hi), Color.WHITE, 1.5)
				draw_line(Vector2(cx - bar * 0.2, y_hi), Vector2(cx + bar * 0.2, y_hi), Color.WHITE, 1.5)
				draw_line(Vector2(cx - bar * 0.2, y_lo), Vector2(cx + bar * 0.2, y_lo), Color.WHITE, 1.5)
			if bar > 26.0:
				var txt := "%d%%" % roundi(v * 100.0) if percent else _short(v)
				_text(Vector2(x - 10, plot.end.y - h - 6), txt, 12, Color(1, 1, 1, 0.85), bar + 20)

	for gi in labels.size():
		var x := plot.position.x + gi * group
		var parts := String(labels[gi]).split(" vs ")
		for li in parts.size():
			var line := parts[li] if li == 0 else "vs " + parts[li]
			_text(Vector2(x, plot.end.y + 22 + li * 17), line, 13, AXIS, group)

	var lx := plot.position.x
	for si in series.size():
		var series_name := String(series[si].get("name", ""))
		draw_rect(Rect2(lx, size.y - 34, 14, 14), COLORS[si % COLORS.size()])
		_text(Vector2(lx + 20, size.y - 22), series_name, 14, Color.WHITE, 260, HORIZONTAL_ALIGNMENT_LEFT)
		lx += 40.0 + _font.get_string_size(series_name, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x


func _text(pos: Vector2, text: String, font_size: int, color: Color, width: float,
		align := HORIZONTAL_ALIGNMENT_CENTER) -> void:
	draw_string(_font, pos, text, align, width, font_size, color)


static func _short(v: float) -> String:
	if absf(v) >= 100.0:
		return "%d" % roundi(v)
	if absf(v) >= 10.0:
		return "%.1f" % v
	return "%.2f" % v
