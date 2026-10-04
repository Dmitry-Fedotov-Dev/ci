// Package golint has one deliberate lint error: selftest checks that go-lint reports it.
package golint

import "encoding/json"

// Parse ignores the decoding error — errcheck must flag this. (Not os.Remove: the
// std-error-handling preset deliberately allows ignoring that one.)
func Parse(data []byte) map[string]any {
	var v map[string]any
	json.Unmarshal(data, &v)
	return v
}
