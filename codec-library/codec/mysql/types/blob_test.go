package types

import (
	"testing"

	"github.com/bindian0509/system-design/codec-library/codec/mysql"
)

func TestBlobCodecCopy(t *testing.T) {
	codec := NewBlobCodec(mysql.TypeBlob)
	meta := mysql.ColumnMeta{Name: "data", Type: mysql.TypeBlob}
	raw := []byte{1, 2, 3}

	val, err := codec.Decode(raw, meta, mysql.Options{})
	if err != nil {
		t.Fatalf("decode failed: %v", err)
	}
	out, ok := val.([]byte)
	if !ok || len(out) != 3 || out[0] != 1 {
		t.Fatalf("unexpected decoded value: %T %v", val, val)
	}
	out[0] = 9
	if raw[0] != 1 {
		t.Fatalf("expected copy; original mutated")
	}
}

func TestBlobCodecZeroCopy(t *testing.T) {
	codec := NewBlobCodec(mysql.TypeBlob)
	meta := mysql.ColumnMeta{Name: "data", Type: mysql.TypeBlob}
	raw := []byte{1, 2, 3}

	val, err := codec.Decode(raw, meta, mysql.Options{ZeroCopy: true})
	if err != nil {
		t.Fatalf("decode failed: %v", err)
	}
	out, ok := val.([]byte)
	if !ok || &out[0] != &raw[0] {
		t.Fatalf("expected zero-copy slice, got %T %v", val, val)
	}
}
