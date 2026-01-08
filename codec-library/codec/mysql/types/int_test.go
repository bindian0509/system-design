package types

import (
	"bytes"
	"testing"

	"github.com/bindian0509/system-design/codec-library/codec/mysql"
)

func TestIntCodecText(t *testing.T) {
	codec := NewIntCodec(mysql.TypeLong, 4)
	meta := mysql.ColumnMeta{Name: "id", Type: mysql.TypeLong}

	buf := new(bytes.Buffer)
	if err := codec.Encode(int64(42), meta, buf, mysql.Options{Protocol: mysql.ProtocolText}); err != nil {
		t.Fatalf("encode failed: %v", err)
	}
	if got := buf.String(); got != "42" {
		t.Fatalf("expected 42, got %s", got)
	}

	val, err := codec.Decode([]byte("42"), meta, mysql.Options{Protocol: mysql.ProtocolText})
	if err != nil {
		t.Fatalf("decode failed: %v", err)
	}
	if v, ok := val.(int64); !ok || v != 42 {
		t.Fatalf("expected int64(42), got %T %v", val, val)
	}
}

func TestIntCodecUnsigned(t *testing.T) {
	codec := NewIntCodec(mysql.TypeLong, 4)
	meta := mysql.ColumnMeta{Name: "count", Type: mysql.TypeLong, Unsigned: true}

	val, err := codec.Decode([]byte("4294967295"), meta, mysql.Options{Protocol: mysql.ProtocolText})
	if err != nil {
		t.Fatalf("decode failed: %v", err)
	}
	if v, ok := val.(uint64); !ok || v != 4294967295 {
		t.Fatalf("expected uint64 max, got %T %v", val, val)
	}
}

func TestIntCodecBinary(t *testing.T) {
	codec := NewIntCodec(mysql.TypeLong, 4)
	meta := mysql.ColumnMeta{Name: "id", Type: mysql.TypeLong}

	buf := new(bytes.Buffer)
	if err := codec.Encode(int32(7), meta, buf, mysql.Options{Protocol: mysql.ProtocolBinary}); err != nil {
		t.Fatalf("binary encode failed: %v", err)
	}
	if got := buf.Bytes(); len(got) != 4 || got[0] != 7 {
		t.Fatalf("unexpected binary encoding: %v", got)
	}

	val, err := codec.Decode(buf.Bytes(), meta, mysql.Options{Protocol: mysql.ProtocolBinary})
	if err != nil {
		t.Fatalf("binary decode failed: %v", err)
	}
	if v, ok := val.(int32); !ok || v != 7 {
		t.Fatalf("expected int32(7), got %T %v", val, val)
	}
}
