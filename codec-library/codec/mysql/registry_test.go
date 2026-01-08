package mysql

import (
	"bytes"
	"testing"
)

type fakeCodec struct {
	code    TypeCode
	decoded any
}

func (f fakeCodec) MySQLType() TypeCode { return f.code }
func (f fakeCodec) Encode(value any, meta ColumnMeta, buf *bytes.Buffer, opts Options) error {
	buf.WriteString("ok")
	return nil
}
func (f fakeCodec) Decode(raw []byte, meta ColumnMeta, opts Options) (any, error) {
	return f.decoded, nil
}

func TestRegistryResolveAndDecode(t *testing.T) {
	r := NewRegistry()
	r.Register(fakeCodec{code: TypeLong, decoded: 42})

	meta := ColumnMeta{Name: "id", Type: TypeLong}
	val, err := r.Decode(meta, []byte("ignored"), Options{})
	if err != nil {
		t.Fatalf("decode failed: %v", err)
	}
	if val != 42 {
		t.Fatalf("expected 42, got %v", val)
	}
}

func TestRegistryColumnOverride(t *testing.T) {
	r := NewRegistry()
	r.Register(fakeCodec{code: TypeLong, decoded: 1})
	r.RegisterColumn("special", fakeCodec{code: TypeBlob, decoded: "override"})

	meta := ColumnMeta{Name: "Special", Type: TypeLong}
	val, err := r.Decode(meta, []byte("ignored"), Options{})
	if err != nil {
		t.Fatalf("decode failed: %v", err)
	}
	if val != "override" {
		t.Fatalf("expected override, got %v", val)
	}
}
