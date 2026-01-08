package types

import (
	"bytes"
	"encoding/json"

	"github.com/bindian0509/system-design/codec-library/codec/mysql"
)

type jsonCodec struct{}

func NewJSONCodec() mysql.Codec {
	return jsonCodec{}
}

func (jsonCodec) MySQLType() mysql.TypeCode {
	return mysql.TypeJSON
}

func (jsonCodec) Encode(value any, meta mysql.ColumnMeta, buf *bytes.Buffer, opts mysql.Options) error {
	switch v := value.(type) {
	case json.RawMessage:
		buf.Write(v)
	case []byte:
		buf.Write(v)
	case string:
		buf.WriteString(v)
	default:
		b, err := json.Marshal(v)
		if err != nil {
			return err
		}
		buf.Write(b)
	}
	return nil
}

func (jsonCodec) Decode(raw []byte, meta mysql.ColumnMeta, opts mysql.Options) (any, error) {
	if opts.ZeroCopy {
		return json.RawMessage(raw), nil
	}
	var out any
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil, err
	}
	return out, nil
}
