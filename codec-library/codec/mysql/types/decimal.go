package types

import (
	"bytes"
	"fmt"
	"math/big"
	"strconv"
	"strings"

	"github.com/bindian0509/system-design/codec-library/codec/mysql"
)

type decimalCodec struct{}

func NewDecimalCodec() mysql.Codec {
	return decimalCodec{}
}

func (decimalCodec) MySQLType() mysql.TypeCode {
	return mysql.TypeNewDecimal
}

func (decimalCodec) Encode(value any, meta mysql.ColumnMeta, buf *bytes.Buffer, opts mysql.Options) error {
	s, err := formatDecimal(value, meta.Scale)
	if err != nil {
		return err
	}
	buf.WriteString(s)
	return nil
}

func (decimalCodec) Decode(raw []byte, meta mysql.ColumnMeta, opts mysql.Options) (any, error) {
	r, ok := new(big.Rat).SetString(string(raw))
	if !ok {
		return nil, fmt.Errorf("mysqlcodec: cannot parse decimal %q", string(raw))
	}
	return r, nil
}

func formatDecimal(value any, scale int) (string, error) {
	switch v := value.(type) {
	case string:
		return normalizeScale(v, scale), nil
	case []byte:
		return normalizeScale(string(v), scale), nil
	case int:
		return intWithScale(int64(v), scale), nil
	case int64:
		return intWithScale(v, scale), nil
	case int32:
		return intWithScale(int64(v), scale), nil
	case int16:
		return intWithScale(int64(v), scale), nil
	case int8:
		return intWithScale(int64(v), scale), nil
	case uint:
		return uintWithScale(uint64(v), scale), nil
	case uint64:
		return uintWithScale(v, scale), nil
	case uint32:
		return uintWithScale(uint64(v), scale), nil
	case uint16:
		return uintWithScale(uint64(v), scale), nil
	case uint8:
		return uintWithScale(uint64(v), scale), nil
	case float64:
		return strconv.FormatFloat(v, 'f', scale, 64), nil
	case float32:
		return strconv.FormatFloat(float64(v), 'f', scale, 32), nil
	case *big.Rat:
		if scale >= 0 {
			return v.FloatString(scale), nil
		}
		return v.RatString(), nil
	case *big.Float:
		if scale >= 0 {
			return v.Text('f', scale), nil
		}
		return v.Text('g', -1), nil
	case *big.Int:
		return intWithScale(v.Int64(), scale), nil
	default:
		return "", mysql.ErrUnsupportedValue
	}
}

func normalizeScale(s string, scale int) string {
	if scale < 0 {
		return s
	}
	if strings.Contains(s, ".") {
		parts := strings.SplitN(s, ".", 2)
		frac := parts[1]
		switch {
		case len(frac) == scale:
			return s
		case len(frac) < scale:
			return parts[0] + "." + frac + strings.Repeat("0", scale-len(frac))
		default:
			return parts[0] + "." + frac[:scale]
		}
	}
	if scale == 0 {
		return s
	}
	return s + "." + strings.Repeat("0", scale)
}

func intWithScale(v int64, scale int) string {
	if scale <= 0 {
		return strconv.FormatInt(v, 10)
	}
	return fmt.Sprintf("%s.%s", strconv.FormatInt(v, 10), strings.Repeat("0", scale))
}

func uintWithScale(v uint64, scale int) string {
	if scale <= 0 {
		return strconv.FormatUint(v, 10)
	}
	return fmt.Sprintf("%s.%s", strconv.FormatUint(v, 10), strings.Repeat("0", scale))
}
