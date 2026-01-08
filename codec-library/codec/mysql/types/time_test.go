package types

import (
	"bytes"
	"testing"
	"time"

	"github.com/bindian0509/system-design/codec-library/codec/mysql"
)

func TestTimestampCodec(t *testing.T) {
	codec := NewTimestampCodec()
	meta := mysql.ColumnMeta{Name: "created_at", Type: mysql.TypeTimestamp, Scale: 3, Location: time.UTC}

	ts := time.Date(2024, 1, 2, 15, 4, 5, 123000000, time.UTC)
	buf := new(bytes.Buffer)
	if err := codec.Encode(ts, meta, buf, mysql.Options{}); err != nil {
		t.Fatalf("encode failed: %v", err)
	}
	if got := buf.String(); got != "2024-01-02 15:04:05.123" {
		t.Fatalf("unexpected encoding: %s", got)
	}

	val, err := codec.Decode([]byte("2024-01-02 15:04:05.123"), meta, mysql.Options{})
	if err != nil {
		t.Fatalf("decode failed: %v", err)
	}
	if out, ok := val.(time.Time); !ok || !out.Equal(ts) {
		t.Fatalf("expected %v, got %T %v", ts, val, val)
	}
}

func TestDateCodec(t *testing.T) {
	codec := NewDateCodec()
	meta := mysql.ColumnMeta{Name: "event_date", Type: mysql.TypeDate}

	val, err := codec.Decode([]byte("2024-12-31"), meta, mysql.Options{})
	if err != nil {
		t.Fatalf("decode failed: %v", err)
	}
	if d, ok := val.(time.Time); !ok || d.Format("2006-01-02") != "2024-12-31" {
		t.Fatalf("unexpected date: %T %v", val, val)
	}
}
