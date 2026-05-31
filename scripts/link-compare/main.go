// link-compare: crawl two sites and diff their internal page sets.
//
// Usage:
//   go run . -a https://kylepounds.com -b http://localhost:8192
//   go run . -a https://kylepounds.com -b https://niski84.github.io/kylepounds-website-fix
//
// Output: paths on A but missing from B, paths only on B, and a summary.
package main

import (
	"flag"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"
)

var hrefRe = regexp.MustCompile(`(?i)href="([^"#?]+)"`)

type crawler struct {
	base    *url.URL
	client  *http.Client
	mu      sync.Mutex
	visited map[string]bool
	queue   []string
	workers int
	delay   time.Duration
}

func newCrawler(baseURL string, workers int, delay time.Duration) (*crawler, error) {
	u, err := url.Parse(strings.TrimRight(baseURL, "/"))
	if err != nil {
		return nil, err
	}
	return &crawler{
		base:    u,
		client:  &http.Client{Timeout: 15 * time.Second},
		visited: make(map[string]bool),
		queue:   []string{u.String() + "/"},
		workers: workers,
		delay:   delay,
	}, nil
}

// normPath returns a canonical path string for deduplication.
func (c *crawler) normPath(raw string) string {
	u, err := url.Parse(raw)
	if err != nil {
		return ""
	}
	p := u.Path
	if p == "" {
		p = "/"
	}
	// Strip GitHub Pages subpath prefix so paths are comparable to kylepounds.com
	if prefix := c.base.Path; prefix != "" && prefix != "/" {
		p = strings.TrimPrefix(p, prefix)
		if p == "" {
			p = "/"
		}
	}
	return p
}

func (c *crawler) isInternal(raw string) bool {
	u, err := url.Parse(raw)
	if err != nil {
		return false
	}
	if u.Host != "" && u.Host != c.base.Host {
		return false
	}
	if u.Scheme != "" && u.Scheme != "http" && u.Scheme != "https" {
		return false
	}
	p := u.Path
	// Only follow HTML-like paths or root
	if p != "" && p != "/" {
		lower := strings.ToLower(p)
		if !strings.HasSuffix(lower, ".html") && !strings.HasSuffix(lower, ".htm") && !strings.HasSuffix(lower, "/") {
			return false
		}
	}
	return true
}

func (c *crawler) resolveURL(base, href string) string {
	baseU, err := url.Parse(base)
	if err != nil {
		return ""
	}
	ref, err := url.Parse(href)
	if err != nil {
		return ""
	}
	resolved := baseU.ResolveReference(ref)
	resolved.Fragment = ""
	resolved.RawQuery = ""
	return resolved.String()
}

func (c *crawler) fetchLinks(pageURL string) []string {
	resp, err := c.client.Get(pageURL)
	if err != nil || resp.StatusCode != 200 {
		return nil
	}
	defer resp.Body.Close()
	ct := resp.Header.Get("Content-Type")
	if !strings.Contains(ct, "html") {
		return nil
	}
	body, err := io.ReadAll(io.LimitReader(resp.Body, 2<<20)) // 2 MB cap
	if err != nil {
		return nil
	}
	var links []string
	for _, m := range hrefRe.FindAllSubmatch(body, -1) {
		href := string(m[1])
		resolved := c.resolveURL(pageURL, href)
		if resolved != "" && c.isInternal(resolved) {
			links = append(links, resolved)
		}
	}
	return links
}

func (c *crawler) Run() map[string]bool {
	sem := make(chan struct{}, c.workers)
	var wg sync.WaitGroup

	for {
		c.mu.Lock()
		if len(c.queue) == 0 {
			c.mu.Unlock()
			wg.Wait()
			c.mu.Lock()
			if len(c.queue) == 0 {
				c.mu.Unlock()
				break
			}
			c.mu.Unlock()
			continue
		}
		next := c.queue[0]
		c.queue = c.queue[1:]
		c.mu.Unlock()

		sem <- struct{}{}
		wg.Add(1)
		go func(pageURL string) {
			defer wg.Done()
			defer func() { <-sem }()
			if c.delay > 0 {
				time.Sleep(c.delay)
			}
			links := c.fetchLinks(pageURL)
			c.mu.Lock()
			defer c.mu.Unlock()
			for _, link := range links {
				norm := c.normPath(link)
				if norm == "" || c.visited[norm] {
					continue
				}
				c.visited[norm] = true
				c.queue = append(c.queue, link)
			}
		}(next)
	}

	// Ensure root is always counted
	result := make(map[string]bool, len(c.visited))
	for p := range c.visited {
		result[p] = true
	}
	if len(result) == 0 {
		result["/"] = true
	}
	return result
}

func setDiff(a, b map[string]bool) []string {
	var diff []string
	for k := range a {
		if !b[k] {
			diff = append(diff, k)
		}
	}
	sort.Strings(diff)
	return diff
}

func main() {
	siteA := flag.String("a", "https://kylepounds.com", "Site A base URL (source of truth)")
	siteB := flag.String("b", "http://localhost:8192", "Site B base URL (our mirror)")
	workersA := flag.Int("wa", 3, "Concurrent workers for site A")
	workersB := flag.Int("wb", 8, "Concurrent workers for site B")
	delayA := flag.Duration("da", 400*time.Millisecond, "Delay between requests to site A (be polite)")
	delayB := flag.Duration("db", 0, "Delay between requests to site B")
	flag.Parse()

	fmt.Printf("Crawling A: %s  (workers=%d delay=%s)\n", *siteA, *workersA, *delayA)
	crawlerA, err := newCrawler(*siteA, *workersA, *delayA)
	if err != nil {
		fmt.Println("bad URL for A:", err)
		return
	}
	pagesA := crawlerA.Run()
	fmt.Printf("  → %d pages found on A\n\n", len(pagesA))

	fmt.Printf("Crawling B: %s  (workers=%d delay=%s)\n", *siteB, *workersB, *delayB)
	crawlerB, err := newCrawler(*siteB, *workersB, *delayB)
	if err != nil {
		fmt.Println("bad URL for B:", err)
		return
	}
	pagesB := crawlerB.Run()
	fmt.Printf("  → %d pages found on B\n\n", len(pagesB))

	onlyA := setDiff(pagesA, pagesB)
	onlyB := setDiff(pagesB, pagesA)
	matched := len(pagesA) - len(onlyA)

	fmt.Printf("━━━ Missing from B (on kylepounds.com but not our mirror) ━━━  %d\n", len(onlyA))
	for _, p := range onlyA {
		fmt.Println(" ", p)
	}

	fmt.Printf("\n━━━ Extra in B (in our mirror but not on kylepounds.com) ━━━  %d\n", len(onlyB))
	for _, p := range onlyB {
		fmt.Println(" ", p)
	}

	fmt.Printf("\n━━━ Summary ━━━\n")
	fmt.Printf("  A (%s): %d pages\n", *siteA, len(pagesA))
	fmt.Printf("  B (%s): %d pages\n", *siteB, len(pagesB))
	fmt.Printf("  Matched:        %d\n", matched)
	fmt.Printf("  Missing from B: %d\n", len(onlyA))
	fmt.Printf("  Extra in B:     %d\n", len(onlyB))
}
