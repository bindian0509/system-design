package types

import (
	"bytes"

	"github.com/bindian0509/system-design/codec-library/codec/mysql"
)

type stringCodec struct {
	code mysql.TypeCode
}

// NewStringCodec handles VARCHAR/TEXT-like types.
func NewStringCodec(code mysql.TypeCode) mysql.Codec {
	return stringCodec{code: code}
}

func (c stringCodec) MySQLType() mysql.TypeCode {
	return c.code
}

func (c stringCodec) Encode(value any, meta mysql.ColumnMeta, buf *bytes.Buffer, opts mysql.Options) error {
	switch v := value.(type) {
	case string:
		buf.WriteString(v)
	case []byte:
		buf.Write(v)
	default:
		return mysql.ErrUnsupportedValue
	}
	return nil
}

func (c stringCodec) Decode(raw []byte, meta mysql.ColumnMeta, opts mysql.Options) (any, error) {
	if opts.ZeroCopy {
		return raw, nil
	}
	return string(raw), nil
}
