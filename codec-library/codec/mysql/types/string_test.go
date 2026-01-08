package types

import (
	"testing"

	"github.com/bindian0509/system-design/codec-library/codec/mysql"
)

func TestStringCodecZeroCopy(t *testing.T) {
	codec := NewStringCodec(mysql.TypeVarchar)
	meta := mysql.ColumnMeta{Name: "name", Type: mysql.TypeVarchar}

	raw := []byte("hello")
	val, err := codec.Decode(raw, meta, mysql.Options{ZeroCopy: true})
	if err != nil {
		t.Fatalf("decode failed: %v", err)
	}
	if v, ok := val.([]byte); !ok || string(v) != "hello" {
		t.Fatalf("expected []byte hello, got %T %v", val, val)
	}
}

func TestStringCodecCopy(t *testing.T) {
	codec := NewStringCodec(mysql.TypeVarchar)
	meta := mysql.ColumnMeta{Name: "name", Type: mysql.TypeVarchar}

	raw := []byte("hello")
	val, err := codec.Decode(raw, meta, mysql.Options{})
	if err != nil {
		t.Fatalf("decode failed: %v", err)
	}
	if v, ok := val.(string); !ok || v != "hello" {
		t.Fatalf("expected string hello, got %T %v", val, val)
	}
}
