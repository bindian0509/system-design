package mysql

import (
	"bytes"
	"fmt"
	"strings"
	"sync"
)

// Registry maps MySQL type metadata to codecs.
type Registry struct {
	types      map[TypeCode]Codec
	overrides  map[string]Codec
	bufferPool sync.Pool
}

// NewRegistry constructs an empty registry. Use a companion package to install defaults.
func NewRegistry() *Registry {
	return &Registry{
		types:     make(map[TypeCode]Codec),
		overrides: make(map[string]Codec),
		bufferPool: sync.Pool{
			New: func() any { return new(bytes.Buffer) },
		},
	}
}

// Register installs a codec for a MySQL type.
func (r *Registry) Register(codec Codec) {
	if codec == nil {
		return
	}
	r.types[codec.MySQLType()] = codec
}

// RegisterColumn installs a per-column override by column name (case-insensitive).
func (r *Registry) RegisterColumn(column string, codec Codec) {
	if codec == nil {
		return
	}
	r.overrides[strings.ToLower(column)] = codec
}

// Resolve chooses the appropriate codec for metadata.
func (r *Registry) Resolve(meta ColumnMeta) (Codec, error) {
	if codec, ok := r.overrides[strings.ToLower(meta.Name)]; ok {
		return codec, nil
	}
	if codec, ok := r.types[meta.Type]; ok {
		return codec, nil
	}
	return nil, fmt.Errorf("mysqlcodec: no codec registered for type %d", meta.Type)
}

func (r *Registry) getBuffer() *bytes.Buffer {
	buf := r.bufferPool.Get().(*bytes.Buffer)
	buf.Reset()
	return buf
}

func (r *Registry) putBuffer(buf *bytes.Buffer) {
	buf.Reset()
	r.bufferPool.Put(buf)
}

// Encode converts a value into its wire representation based on column metadata.
func (r *Registry) Encode(meta ColumnMeta, value any, opts Options) ([]byte, error) {
	codec, err := r.Resolve(meta)
	if err != nil {
		return nil, err
	}
	if value == nil {
		return nil, nil
	}

	buf := r.getBuffer()
	defer r.putBuffer(buf)

	if err := codec.Encode(value, meta, buf, opts); err != nil {
		return nil, err
	}

	out := make([]byte, buf.Len())
	copy(out, buf.Bytes())
	return out, nil
}

// Decode converts raw bytes into a Go value using the resolved codec.
func (r *Registry) Decode(meta ColumnMeta, raw []byte, opts Options) (any, error) {
	codec, err := r.Resolve(meta)
	if err != nil {
		return nil, err
	}
	if raw == nil {
		return nil, nil
	}
	return codec.Decode(raw, meta, opts)
}
