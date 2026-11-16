extends Node
## Autoload "Net": klient WebSocket serwera Pythona (`python -m bomberman serve`).

signal connected(hello: Dictionary)
signal disconnected
signal message(msg: Dictionary)

const URL := "ws://127.0.0.1:8765"
const RETRY_SECONDS := 2.0
# powtórki mają kilka MB, domyślny bufor to 64 KiB
const BUFFER_BYTES := 16 * 1024 * 1024

var hello: Dictionary = {}
var enabled := true

var _ws: WebSocketPeer
var _last_state := WebSocketPeer.STATE_CLOSED
var _retry := 0.0


func _ready() -> void:
	if "--offline" in OS.get_cmdline_user_args():
		enabled = false


func is_open() -> bool:
	return _ws != null and _ws.get_ready_state() == WebSocketPeer.STATE_OPEN


func send(msg: Dictionary) -> bool:
	if not is_open():
		return false
	_ws.send_text(JSON.stringify(msg))
	return true


func _process(delta: float) -> void:
	if not enabled:
		return
	if _ws == null:
		_retry -= delta
		if _retry <= 0.0:
			_open()
		return
	_ws.poll()
	var state := _ws.get_ready_state()
	if state == WebSocketPeer.STATE_OPEN:
		while _ws.get_available_packet_count() > 0:
			var data: Variant = JSON.parse_string(_ws.get_packet().get_string_from_utf8())
			if typeof(data) != TYPE_DICTIONARY:
				continue
			if data.get("type", "") == "hello":
				hello = data
				connected.emit(data)
			message.emit(data)
	elif state == WebSocketPeer.STATE_CLOSED:
		var was_open := _last_state == WebSocketPeer.STATE_OPEN
		_ws = null
		_retry = RETRY_SECONDS
		if was_open:
			hello = {}
			disconnected.emit()
	_last_state = state


func _open() -> void:
	_ws = WebSocketPeer.new()
	_ws.inbound_buffer_size = BUFFER_BYTES
	_ws.outbound_buffer_size = 1024 * 1024
	if _ws.connect_to_url(URL) != OK:
		_ws = null
		_retry = RETRY_SECONDS
	_last_state = WebSocketPeer.STATE_CONNECTING
