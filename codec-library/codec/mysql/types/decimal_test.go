package types

import (
	"bytes"
	"math/big"
	"testing"

	"github.com/bindian0509/system-design/codec-library/codec/mysql"
)

func TestDecimalCodec(t *testing.T) {
	codec := NewDecimalCodec()
	meta := mysql.ColumnMeta{Name: "amount", Type: mysql.TypeNewDecimal, Scale: 2}

	buf := new(bytes.Buffer)
	val := big.NewRat(12345, 100) // 123.45
	if err := codec.Encode(val, meta, buf, mysql.Options{}); err != nil {
		t.Fatalf("encode failed: %v", err)
	}
	if got := buf.String(); got != "123.45" {
		t.Fatalf("expected 123.45, got %s", got)
	}

	out, err := codec.Decode([]byte("123.45"), meta, mysql.Options{})
	if err != nil {
		t.Fatalf("decode failed: %v", err)
	}
	if r, ok := out.(*big.Rat); !ok || r.FloatString(2) != "123.45" {
		t.Fatalf("expected *big.Rat 123.45, got %T %v", out, out)
	}
}
