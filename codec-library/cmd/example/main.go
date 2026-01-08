package main

import (
	"fmt"
	"math/big"
	"time"

	"github.com/bindian0509/system-design/codec-library/codec/mysql"
	mysqltypes "github.com/bindian0509/system-design/codec-library/codec/mysql/types"
)

func main() {
	reg := mysqltypes.DefaultRegistry()
	opts := mysql.Options{Protocol: mysql.ProtocolText}

	// DECIMAL round-trip
	amountMeta := mysql.ColumnMeta{Name: "amount", Type: mysql.TypeNewDecimal, Scale: 2}
	amount := big.NewRat(12345, 100) // 123.45
	amountBytes, _ := reg.Encode(amountMeta, amount, opts)
	fmt.Printf("encoded DECIMAL: %s\n", string(amountBytes))

	decodedAmount, _ := reg.Decode(amountMeta, amountBytes, opts)
	fmt.Printf("decoded DECIMAL as *big.Rat: %s\n", decodedAmount.(*big.Rat).FloatString(2))

	// TIMESTAMP round-trip
	tsMeta := mysql.ColumnMeta{Name: "created_at", Type: mysql.TypeTimestamp, Scale: 3, Location: time.UTC}
	now := time.Date(2024, 1, 2, 15, 4, 5, 123000000, time.UTC)
	tsBytes, _ := reg.Encode(tsMeta, now, opts)
	tsValue, _ := reg.Decode(tsMeta, tsBytes, opts)
	fmt.Printf("timestamp round-trip: %s\n", tsValue.(time.Time).Format(time.RFC3339Nano))

	// JSON round-trip
	jsonMeta := mysql.ColumnMeta{Name: "payload", Type: mysql.TypeJSON}
	jsonBytes, _ := reg.Encode(jsonMeta, map[string]any{"ok": true, "count": 3}, opts)
	jsonValue, _ := reg.Decode(jsonMeta, jsonBytes, opts)
	fmt.Printf("json decoded as %T => %v\n", jsonValue, jsonValue)
}
