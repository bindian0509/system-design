package types

import (
	"bytes"
	"encoding/binary"
	"fmt"
	"strconv"

	"github.com/bindian0509/system-design/codec-library/codec/mysql"
)

type intCodec struct {
	code mysql.TypeCode
	size int
}

// NewIntCodec creates a codec for the given MySQL integer type.
func NewIntCodec(code mysql.TypeCode, size int) mysql.Codec {
	return intCodec{code: code, size: size}
}

func (c intCodec) MySQLType() mysql.TypeCode {
	return c.code
}

func (c intCodec) Encode(value any, meta mysql.ColumnMeta, buf *bytes.Buffer, opts mysql.Options) error {
	if value == nil {
		return nil
	}

	if opts.Protocol == mysql.ProtocolBinary {
		return c.encodeBinary(value, meta, buf)
	}
	return c.encodeText(value, meta, buf)
}

func (c intCodec) encodeText(value any, meta mysql.ColumnMeta, buf *bytes.Buffer) error {
	switch v := value.(type) {
	case int64:
		if meta.Unsigned && v < 0 {
			return fmt.Errorf("mysqlcodec: negative value for UNSIGNED column %s", meta.Name)
		}
		buf.WriteString(strconv.FormatInt(v, 10))
	case int, int32, int16, int8:
		n := reflectInt64(v)
		if meta.Unsigned && n < 0 {
			return fmt.Errorf("mysqlcodec: negative value for UNSIGNED column %s", meta.Name)
		}
		buf.WriteString(strconv.FormatInt(n, 10))
	case uint64, uint, uint32, uint16, uint8:
		n := reflectUint64(v)
		if !meta.Unsigned && n > uint64(1<<63-1) {
			return fmt.Errorf("mysqlcodec: uint %d overflows signed column %s", n, meta.Name)
		}
		buf.WriteString(strconv.FormatUint(n, 10))
	case string:
		buf.WriteString(v)
	default:
		return mysql.ErrUnsupportedValue
	}
	return nil
}

func (c intCodec) encodeBinary(value any, meta mysql.ColumnMeta, buf *bytes.Buffer) error {
	var u uint64
	switch v := value.(type) {
	case int64:
		if meta.Unsigned && v < 0 {
			return fmt.Errorf("mysqlcodec: negative value for UNSIGNED column %s", meta.Name)
		}
		u = uint64(v)
	case int, int32, int16, int8:
		n := reflectInt64(v)
		if meta.Unsigned && n < 0 {
			return fmt.Errorf("mysqlcodec: negative value for UNSIGNED column %s", meta.Name)
		}
		u = uint64(n)
	case uint64, uint, uint32, uint16, uint8:
		u = reflectUint64(v)
	default:
		return mysql.ErrUnsupportedValue
	}

	tmp := make([]byte, c.size)
	switch c.size {
	case 2:
		binary.LittleEndian.PutUint16(tmp, uint16(u))
	case 4:
		binary.LittleEndian.PutUint32(tmp, uint32(u))
	case 8:
		binary.LittleEndian.PutUint64(tmp, u)
	default:
		return fmt.Errorf("mysqlcodec: unsupported integer size %d", c.size)
	}
	buf.Write(tmp)
	return nil
}

func (c intCodec) Decode(raw []byte, meta mysql.ColumnMeta, opts mysql.Options) (any, error) {
	if opts.Protocol == mysql.ProtocolBinary {
		return c.decodeBinary(raw, meta)
	}
	return c.decodeText(raw, meta)
}

func (c intCodec) decodeText(raw []byte, meta mysql.ColumnMeta) (any, error) {
	if meta.Unsigned {
		u, err := strconv.ParseUint(string(raw), 10, 64)
		if err != nil {
			return nil, err
		}
		return u, nil
	}
	i, err := strconv.ParseInt(string(raw), 10, 64)
	if err != nil {
		return nil, err
	}
	return i, nil
}

func (c intCodec) decodeBinary(raw []byte, meta mysql.ColumnMeta) (any, error) {
	if len(raw) < c.size {
		return nil, fmt.Errorf("mysqlcodec: binary integer expected %d bytes, got %d", c.size, len(raw))
	}
	switch c.size {
	case 2:
		u := binary.LittleEndian.Uint16(raw)
		if meta.Unsigned {
			return uint64(u), nil
		}
		return int16(u), nil
	case 4:
		u := binary.LittleEndian.Uint32(raw)
		if meta.Unsigned {
			return uint64(u), nil
		}
		return int32(u), nil
	case 8:
		u := binary.LittleEndian.Uint64(raw)
		if meta.Unsigned {
			return u, nil
		}
		return int64(u), nil
	default:
		return nil, fmt.Errorf("mysqlcodec: unsupported integer size %d", c.size)
	}
}

func reflectInt64(v any) int64 {
	switch n := v.(type) {
	case int:
		return int64(n)
	case int32:
		return int64(n)
	case int16:
		return int64(n)
	case int8:
		return int64(n)
	}
	return v.(int64)
}

func reflectUint64(v any) uint64 {
	switch n := v.(type) {
	case uint:
		return uint64(n)
	case uint32:
		return uint64(n)
	case uint16:
		return uint64(n)
	case uint8:
		return uint64(n)
	}
	return v.(uint64)
}
