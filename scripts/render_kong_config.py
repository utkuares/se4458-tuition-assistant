import argparse
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", default="http://host.docker.internal:8000",
                        help="URL of the tuition API as seen from the gateway.")
    parser.add_argument("--output", default="gateway/kong.yml", help="Where to write the config.")
    args = parser.parse_args()

    public_key = (ROOT / "keys" / "jwt_public.pem").read_text().strip()
    indented_key = "\n".join("          " + line for line in public_key.splitlines())

    template = Template((ROOT / "gateway" / "kong.template.yml").read_text())
    output = template.substitute(UPSTREAM_URL=args.upstream, JWT_PUBLIC_KEY=indented_key)
    (ROOT / args.output).write_text(output)
    print(f"Wrote {args.output} (upstream: {args.upstream})")


if __name__ == "__main__":
    main()