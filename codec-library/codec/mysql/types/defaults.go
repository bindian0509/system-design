package types

import "github.com/bindian0509/system-design/codec-library/codec/mysql"

// DefaultRegistry returns a registry preloaded with common codecs.
func DefaultRegistry() *mysql.Registry {
	r := mysql.NewRegistry()
	RegisterDefaults(r)
	return r
}

// RegisterDefaults installs the built-in codecs into the provided registry.
func RegisterDefaults(r *mysql.Registry) {
	r.Register(NewIntCodec(mysql.TypeShort, 2))     // SMALLINT
	r.Register(NewIntCodec(mysql.TypeLong, 4))      // INT
	r.Register(NewIntCodec(mysql.TypeLongLong, 8))  // BIGINT
	r.Register(NewStringCodec(mysql.TypeVarchar))   // VARCHAR
	r.Register(NewStringCodec(mysql.TypeVarString)) // VARSTRING
	r.Register(NewStringCodec(mysql.TypeString))    // TEXT/CHAR
	r.Register(NewDecimalCodec())                   // DECIMAL/NUMERIC
	r.Register(NewDateCodec())
	r.Register(NewDateTimeCodec())
	r.Register(NewTimestampCodec())
	r.Register(NewJSONCodec())
	r.Register(NewBlobCodec(mysql.TypeBlob))
	r.Register(NewBlobCodec(mysql.TypeTinyBlob))
	r.Register(NewBlobCodec(mysql.TypeMediumBlob))
	r.Register(NewBlobCodec(mysql.TypeLongBlob))
}
