package types

import (
	"bytes"
	"strings"
	"time"

	"github.com/bindian0509/system-design/codec-library/codec/mysql"
)

type timeCodec struct {
	code mysql.TypeCode
}

func NewDateCodec() mysql.Codec {
	return timeCodec{code: mysql.TypeDate}
}

func NewDateTimeCodec() mysql.Codec {
	return timeCodec{code: mysql.TypeDatetime}
}

func NewTimestampCodec() mysql.Codec {
	return timeCodec{code: mysql.TypeTimestamp}
}

func (c timeCodec) MySQLType() mysql.TypeCode {
	return c.code
}

func (c timeCodec) Encode(value any, meta mysql.ColumnMeta, buf *bytes.Buffer, opts mysql.Options) error {
	switch v := value.(type) {
	case time.Time:
		loc := effectiveTZ(meta, opts)
		ts := formatTime(v.In(loc), meta.Scale, c.code == mysql.TypeDate)
		buf.WriteString(ts)
		return nil
	case string:
		buf.WriteString(v)
		return nil
	default:
		return mysql.ErrUnsupportedValue
	}
}

func (c timeCodec) Decode(raw []byte, meta mysql.ColumnMeta, opts mysql.Options) (any, error) {
	loc := effectiveTZ(meta, opts)
	str := string(raw)

	if c.code == mysql.TypeDate {
		return time.ParseInLocation("2006-01-02", str, loc)
	}

	layout := "2006-01-02 15:04:05"
	if dot := strings.IndexByte(str, '.'); dot != -1 {
		fracLen := len(str) - dot - 1
		if fracLen > 0 {
			layout += "." + strings.Repeat("0", fracLen)
		}
	}
	return time.ParseInLocation(layout, str, loc)
}

func formatTime(t time.Time, scale int, dateOnly bool) string {
	if dateOnly {
		return t.Format("2006-01-02")
	}

	layout := "2006-01-02 15:04:05"
	if scale > 0 {
		layout += "." + strings.Repeat("0", scale)
	}
	return t.Format(layout)
}

func effectiveTZ(meta mysql.ColumnMeta, opts mysql.Options) *time.Location {
	if meta.Location != nil {
		return meta.Location
	}
	if opts.Location != nil {
		return opts.Location
	}
	return time.UTC
}
