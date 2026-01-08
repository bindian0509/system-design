package types

import (
	"encoding/json"
	"testing"

	"github.com/bindian0509/system-design/codec-library/codec/mysql"
)

func TestJSONCodec(t *testing.T) {
	codec := NewJSONCodec()
	meta := mysql.ColumnMeta{Name: "payload", Type: mysql.TypeJSON}

	raw := []byte(`{"ok":true,"count":3}`)
	val, err := codec.Decode(raw, meta, mysql.Options{})
	if err != nil {
		t.Fatalf("decode failed: %v", err)
	}
	m, ok := val.(map[string]any)
	if !ok {
		t.Fatalf("expected map, got %T", val)
	}
	if m["ok"] != true || m["count"].(float64) != 3 {
		t.Fatalf("unexpected map contents: %v", m)
	}
}

func TestJSONZeroCopy(t *testing.T) {
	codec := NewJSONCodec()
	meta := mysql.ColumnMeta{Name: "payload", Type: mysql.TypeJSON}
	raw := []byte(`{"a":1}`)

	val, err := codec.Decode(raw, meta, mysql.Options{ZeroCopy: true})
	if err != nil {
		t.Fatalf("decode failed: %v", err)
	}
	msg, ok := val.(json.RawMessage)
	if !ok || string(msg) != `{"a":1}` {
		t.Fatalf("expected zero-copy RawMessage, got %T %v", val, val)
	}
}
