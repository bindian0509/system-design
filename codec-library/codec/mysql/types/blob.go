package types

import (
	"bytes"

	"github.com/bindian0509/system-design/codec-library/codec/mysql"
)

type blobCodec struct {
	code mysql.TypeCode
}

func NewBlobCodec(code mysql.TypeCode) mysql.Codec {
	return blobCodec{code: code}
}

func (b blobCodec) MySQLType() mysql.TypeCode {
	return b.code
}

func (b blobCodec) Encode(value any, meta mysql.ColumnMeta, buf *bytes.Buffer, opts mysql.Options) error {
	switch v := value.(type) {
	case []byte:
		buf.Write(v)
	case string:
		buf.WriteString(v)
	default:
		return mysql.ErrUnsupportedValue
	}
	return nil
}

func (b blobCodec) Decode(raw []byte, meta mysql.ColumnMeta, opts mysql.Options) (any, error) {
	if opts.ZeroCopy {
		return raw, nil
	}
	out := make([]byte, len(raw))
	copy(out, raw)
	return out, nil
}
