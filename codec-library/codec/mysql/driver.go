package mysql

import (
	"database/sql"
	"database/sql/driver"
	"fmt"
	"reflect"
)

// Scanner plugs the registry into database/sql.Scan.
type Scanner struct {
	Registry *Registry
	Meta     ColumnMeta
	Opts     Options
	Dest     any
}

// NewScanner wraps a destination pointer with codec-aware scanning.
func NewScanner(reg *Registry, meta ColumnMeta, opts Options, dest any) *Scanner {
	return &Scanner{
		Registry: reg,
		Meta:     meta,
		Opts:     opts,
		Dest:     dest,
	}
}

// Scan implements database/sql.Scanner.
func (s *Scanner) Scan(src any) error {
	var raw []byte
	switch v := src.(type) {
	case nil:
		raw = nil
	case []byte:
		raw = v
	case string:
		raw = []byte(v)
	case sql.RawBytes:
		raw = v
	default:
		return fmt.Errorf("mysqlcodec: unsupported Scan source %T", src)
	}

	val, err := s.Registry.Decode(s.Meta, raw, s.Opts)
	if err != nil {
		return err
	}
	return assignValue(s.Dest, val)
}

// EncodeValue returns a driver.Value suitable for use with database/sql.
func (r *Registry) EncodeValue(meta ColumnMeta, v any, opts Options) (driver.Value, error) {
	b, err := r.Encode(meta, v, opts)
	if err != nil {
		return nil, err
	}
	if b == nil {
		return nil, nil
	}
	return driver.Value(b), nil
}

func assignValue(dest any, value any) error {
	if dest == nil {
		return fmt.Errorf("mysqlcodec: destination is nil")
	}
	rv := reflect.ValueOf(dest)
	if rv.Kind() != reflect.Ptr || rv.IsNil() {
		return fmt.Errorf("mysqlcodec: destination must be a non-nil pointer")
	}

	if value == nil {
		rv.Elem().Set(reflect.Zero(rv.Elem().Type()))
		return nil
	}

	v := reflect.ValueOf(value)

	// Direct assign.
	if v.Type().AssignableTo(rv.Elem().Type()) {
		rv.Elem().Set(v)
		return nil
	}

	// Convertible types (e.g., []byte -> string).
	if v.Type().ConvertibleTo(rv.Elem().Type()) {
		rv.Elem().Set(v.Convert(rv.Elem().Type()))
		return nil
	}

	// Allow interface targets.
	if rv.Elem().Kind() == reflect.Interface && v.Type().AssignableTo(rv.Elem().Type()) {
		rv.Elem().Set(v)
		return nil
	}

	return fmt.Errorf("mysqlcodec: cannot assign %T to %T", value, dest)
}
