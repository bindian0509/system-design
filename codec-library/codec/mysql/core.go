package mysql

import (
	"bytes"
	"errors"
	"time"
)

// Protocol describes the wire representation used by MySQL.
// Text is used for simple queries; Binary is used for prepared statements.
type Protocol int

const (
	ProtocolText Protocol = iota
	ProtocolBinary
)

// TypeCode matches MySQL column type codes used on the wire.
type TypeCode uint8

const (
	TypeDecimal    TypeCode = 0x00
	TypeTiny       TypeCode = 0x01
	TypeShort      TypeCode = 0x02
	TypeLong       TypeCode = 0x03
	TypeFloat      TypeCode = 0x04
	TypeDouble     TypeCode = 0x05
	TypeNull       TypeCode = 0x06
	TypeTimestamp  TypeCode = 0x07
	TypeLongLong   TypeCode = 0x08
	TypeInt24      TypeCode = 0x09
	TypeDate       TypeCode = 0x0a
	TypeTime       TypeCode = 0x0b
	TypeDatetime   TypeCode = 0x0c
	TypeYear       TypeCode = 0x0d
	TypeNewDate    TypeCode = 0x0e
	TypeVarchar    TypeCode = 0x0f
	TypeBit        TypeCode = 0x10
	TypeJSON       TypeCode = 0xf5
	TypeNewDecimal TypeCode = 0xf6
	TypeEnum       TypeCode = 0xf7
	TypeSet        TypeCode = 0xf8
	TypeTinyBlob   TypeCode = 0xf9
	TypeMediumBlob TypeCode = 0xfa
	TypeLongBlob   TypeCode = 0xfb
	TypeBlob       TypeCode = 0xfc
	TypeVarString  TypeCode = 0xfd
	TypeString     TypeCode = 0xfe
	TypeGeometry   TypeCode = 0xff
)

// ColumnMeta carries metadata emitted by the MySQL server for a column.
type ColumnMeta struct {
	Name     string
	Type     TypeCode
	Length   int  // max length in bytes (as reported by server)
	Scale    int  // decimal scale or fractional seconds precision
	Unsigned bool // true when column is UNSIGNED
	Nullable bool
	Location *time.Location // optional column-specific timezone hint
}

// Options tune codec behavior per call.
type Options struct {
	Protocol Protocol
	ZeroCopy bool           // if true, decoders may return slices referencing input
	Location *time.Location // fallback timezone for temporal codecs
}

// Codec converts between wire-level []byte values and user values.
type Codec interface {
	MySQLType() TypeCode
	Encode(value any, meta ColumnMeta, buf *bytes.Buffer, opts Options) error
	Decode(raw []byte, meta ColumnMeta, opts Options) (any, error)
}

var (
	// ErrNull indicates a NULL value when a non-null target is required.
	ErrNull = errors.New("mysqlcodec: value is NULL")
	// ErrUnsupportedValue indicates a value could not be encoded/decoded.
	ErrUnsupportedValue = errors.New("mysqlcodec: unsupported value for codec")
)

func effectiveLocation(meta ColumnMeta, opts Options) *time.Location {
	if meta.Location != nil {
		return meta.Location
	}
	if opts.Location != nil {
		return opts.Location
	}
	return time.UTC
}
