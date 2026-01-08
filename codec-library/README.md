# codec-library

Go codecs for MySQL column types with a balanced focus on performance and ergonomics. Provides a registry-driven API, text/binary protocol support, zero-copy optional decoding, and `database/sql` helpers plus a runnable example.

## Features
- Registry-based codec resolution per column (type + column override).
- Text and binary protocol encode/decode paths.
- Zero-copy decoding opt-in for `[]byte`/`json.RawMessage`.
- Timezone-aware temporal codecs with scale (fractional seconds) support.
- Helpers to integrate with `database/sql` scanners and drivers.
- Table-driven tests covering edge cases (NULLs, unsigned ints, decimals, timezones, blobs).

## Install
```bash
go get github.com/bindian0509/system-design/codec-library
```

## Quick start
```go
import (
    "time"
    "github.com/bindian0509/system-design/codec-library/codec/mysql"
    mysqltypes "github.com/bindian0509/system-design/codec-library/codec/mysql/types"
)

reg := mysqltypes.DefaultRegistry()
opts := mysql.Options{Protocol: mysql.ProtocolText}

meta := mysql.ColumnMeta{Name: "created_at", Type: mysql.TypeTimestamp, Scale: 3, Location: time.UTC}
ts := time.Now().UTC()

raw, _ := reg.Encode(meta, ts, opts)
decoded, _ := reg.Decode(meta, raw, opts)
_ = decoded.(time.Time) // safe type assertion
```

## Available codecs
- Integers: SMALLINT/INT/BIGINT (signed/unsigned, text and binary)
- Strings: VARCHAR/VARSTRING/STRING (TEXT/CHAR-like)
- DECIMAL/NUMERIC with scale handling (`*big.Rat` friendly)
- Temporal: DATE, DATETIME, TIMESTAMP with fractional seconds
- JSON with optional zero-copy `json.RawMessage`
- BLOB family with optional zero-copy `[]byte`

## Zero-copy decoding
Pass `Options{ZeroCopy: true}` to let decoders return slices pointing at the input buffer. Use only when the underlying buffer outlives the decoded value; otherwise keep the default safe copy behavior.

## database/sql helpers
- `mysql.Scanner` wraps a destination to decode using registry + column metadata.
- `Registry.EncodeValue` produces `driver.Value` suitable for parameter binding.

## Example app
`cmd/example/main.go` demonstrates DECIMAL, TIMESTAMP, and JSON round-trips. Run it with:
```bash
cd codec-library
go run ./cmd/example
```

## Testing
```bash
cd codec-library
go test ./...
```

## Extending
- Implement `mysql.Codec` (define `MySQLType`, `Encode`, `Decode`).
- Register globally via `RegisterDefaults` or per-column with `Registry.RegisterColumn`.
- Use `ColumnMeta.Location` or `Options.Location` to control temporal conversions.

