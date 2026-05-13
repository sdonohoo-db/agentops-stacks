#!/bin/bash
#
# agentops-stacks plugin installer
#
# Installs the agentops-stacks skill into a project (.claude/skills/agentops-stacks/),
# bundling the canonical DAB template tree, library, and schema alongside the
# skill so the renderer is self-contained.
#
# Mirrors the ai-dev-kit databricks-skills installer pattern:
#   ./install_skills.sh                              # install from local repo
#   ./install_skills.sh --install-to-genie           # also upload to workspace
#   ./install_skills.sh --install-to-genie --profile prod
#   ./install_skills.sh --list
#   ./install_skills.sh --help
#
# Remote install (curl) ships once v2 lands on the public repo; until then,
# install from a local clone.

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SKILL_NAME="agentops-stacks"
SKILLS_DIR=".claude/skills"
INSTALL_TO_GENIE=false
DB_PROFILE="${DATABRICKS_CONFIG_PROFILE:-DEFAULT}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Repo root is two levels up from plugin/skills/.
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

show_help() {
    echo -e "${BLUE}agentops-stacks Skills Installer${NC}"
    echo ""
    echo "Usage:"
    echo "  ./install_skills.sh [options]"
    echo ""
    echo "Options:"
    echo "  --help, -h              Show this help message"
    echo "  --list, -l              List available skills"
    echo "  --install-to-genie      Also upload .claude/skills to workspace"
    echo "                          /Users/<you>/.assistant/skills for Genie Code"
    echo "  --profile <name>        Databricks CLI profile (default: DEFAULT or \$DATABRICKS_CONFIG_PROFILE)"
    echo ""
    echo "Examples:"
    echo "  ./install_skills.sh                                # Install agentops-stacks skill"
    echo "  ./install_skills.sh --install-to-genie             # Install + upload to workspace"
    echo "  ./install_skills.sh --install-to-genie --profile prod"
    echo ""
    echo -e "${GREEN}Available skills:${NC}"
    echo "  - agentops-stacks: Scaffold a new DAB project with CI/CD and UC conventions"
    echo ""
}

list_skills() {
    echo -e "${BLUE}Available Skills:${NC}"
    echo ""
    echo -e "  ${GREEN}agentops-stacks${NC}"
    echo "    Scaffold a new DAB project (dev/staging/prod, UC conventions, CI/CD)"
    echo ""
}

install_agentops_stacks_skill() {
    local dest="$SKILLS_DIR/$SKILL_NAME"
    local src="$SCRIPT_DIR/$SKILL_NAME"

    if [ ! -f "$src/SKILL.md" ]; then
        echo -e "${RED}Error: SKILL.md not found at $src${NC}"
        return 1
    fi
    if [ ! -f "$src/render.py" ]; then
        echo -e "${RED}Error: render.py not found at $src${NC}"
        return 1
    fi
    if [ ! -d "$REPO_ROOT/template" ]; then
        echo -e "${RED}Error: template/ not found at $REPO_ROOT/template${NC}"
        return 1
    fi

    rm -rf "$dest"
    mkdir -p "$dest"

    cp "$src/SKILL.md" "$dest/SKILL.md"
    cp "$src/render.py" "$dest/render.py"
    cp "$REPO_ROOT/databricks_template_schema.json" "$dest/databricks_template_schema.json"
    cp -R "$REPO_ROOT/template" "$dest/template"
    if [ -d "$REPO_ROOT/library" ]; then
        cp -R "$REPO_ROOT/library" "$dest/library"
    fi

    echo -e "  ${GREEN}✓${NC} SKILL.md"
    echo -e "  ${GREEN}✓${NC} render.py"
    echo -e "  ${GREEN}✓${NC} databricks_template_schema.json"
    echo -e "  ${GREEN}✓${NC} template/ (bundled)"
    [ -d "$dest/library" ] && echo -e "  ${GREEN}✓${NC} library/ (bundled)"
}

upload_skill_to_genie_workspace() {
    local skill_dir="$1"
    local skills_path="$2"
    local db_profile="$3"

    skill_dir="${skill_dir%/}"
    local skill_name
    skill_name=$(basename "$skill_dir")

    if [[ ! -f "$skill_dir/SKILL.md" ]]; then
        return 0
    fi

    echo -e "  ${GREEN}Uploading${NC} $skill_name"
    databricks workspace mkdirs "$skills_path/$skill_name" --profile "$db_profile" 2>/dev/null || true

    # Upload everything under the skill dir, excluding only VCS junk. Filtering
    # by extension dropped placeholder files (e.g. src/.gitkeep) and silently
    # broke the rendered output, so we no-allowlist and exclude known junk.
    while IFS= read -r -d '' file; do
        rel_path="${file#$skill_dir/}"
        dest_path="$skills_path/$skill_name/$rel_path"
        parent_dir=$(dirname "$dest_path")
        if [[ "$parent_dir" != "$skills_path/$skill_name" ]]; then
            databricks workspace mkdirs "$parent_dir" --profile "$db_profile" 2>/dev/null || true
        fi
        databricks workspace import "$dest_path" --file "$file" --profile "$db_profile" --format AUTO --overwrite 2>/dev/null || true
    done < <(find "$skill_dir" -type f \
        -not -path '*/.git/*' \
        -not -path '*/__pycache__/*' \
        -not -name '*.pyc' \
        -not -name '.DS_Store' \
        -print0)
}

install_skills_to_genie_workspace() {
    if ! command -v databricks >/dev/null 2>&1; then
        echo -e "${RED}Error: databricks CLI not found. Install it to use --install-to-genie.${NC}"
        return 1
    fi

    if [ ! -d "$SKILLS_DIR" ]; then
        echo -e "${RED}Error: $SKILLS_DIR not found (run from the directory where skills were installed).${NC}"
        return 1
    fi
    local abs_skills_dir
    abs_skills_dir="$(cd "$SKILLS_DIR" && pwd)"

    echo ""
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  Uploading skills to workspace (Genie Code)${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo -e "Databricks profile: ${DB_PROFILE}"
    echo -e "Local skills: ${SKILLS_DIR}/ → ${abs_skills_dir}"
    echo ""

    local user_name
    user_name=$(databricks current-user me --profile "$DB_PROFILE" --output json 2>/dev/null | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('userName', ''))" 2>/dev/null || echo "")
    if [ -z "$user_name" ]; then
        echo -e "${RED}Error: Could not determine workspace user. Check auth and --profile.${NC}"
        return 1
    fi

    local skills_path="/Users/$user_name/.assistant/skills"
    echo -e "Workspace user: ${user_name}"
    echo -e "Workspace path: ${skills_path}"
    echo ""

    echo -e "${GREEN}Creating workspace skills directory...${NC}"
    databricks workspace mkdirs "$skills_path" --profile "$DB_PROFILE" 2>/dev/null || true

    echo -e "${GREEN}Uploading skills...${NC}"
    local skill_dir
    for skill_dir in "$abs_skills_dir"/*/; do
        [ -d "$skill_dir" ] || continue
        upload_skill_to_genie_workspace "$skill_dir" "$skills_path" "$DB_PROFILE"
    done

    echo ""
    echo -e "${GREEN}Workspace listing:${NC}"
    databricks workspace list "$skills_path" --profile "$DB_PROFILE" 2>/dev/null || echo -e "  ${YELLOW}(Could not list workspace path)${NC}"

    echo ""
    echo -e "${GREEN}Genie Code upload complete.${NC}"
    echo ""
    return 0
}

# Argument parsing
while [ $# -gt 0 ]; do
    case $1 in
        --help|-h)
            show_help
            exit 0
            ;;
        --list|-l)
            list_skills
            exit 0
            ;;
        --install-to-genie|--deploy-to-assistant)
            INSTALL_TO_GENIE=true
            shift
            ;;
        --profile)
            if [ -z "$2" ] || [ "${2:0:1}" = "-" ]; then
                echo -e "${RED}Error: --profile requires a profile name${NC}"
                exit 1
            fi
            DB_PROFILE="$2"
            shift 2
            ;;
        -*)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information."
            exit 1
            ;;
        *)
            echo -e "${RED}Unknown argument: $1${NC}"
            echo "This installer only supports flags. Use --help for usage."
            exit 1
            ;;
    esac
done

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          agentops-stacks Plugin Installer                  ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

if [ ! -d ".git" ] && [ ! -f "pyproject.toml" ] && [ ! -f "package.json" ] && [ ! -f "databricks.yml" ]; then
    echo -e "${YELLOW}Warning: This doesn't look like a project root directory.${NC}"
    echo -e "Current directory: $(pwd)"
    read -p "Continue anyway? (y/N): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo "Aborted."
        exit 1
    fi
fi

if [ ! -d "$SKILLS_DIR" ]; then
    echo -e "${GREEN}Creating $SKILLS_DIR directory...${NC}"
    mkdir -p "$SKILLS_DIR"
fi

echo -e "${BLUE}Installing from: ${REPO_ROOT}${NC}"
echo ""
echo -e "${GREEN}Installing agentops-stacks skill...${NC}"
install_agentops_stacks_skill

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Installation complete!${NC}"
echo -e "${BLUE}Skill installed to: ${SKILLS_DIR}/${SKILL_NAME}${NC}"
echo ""

if [ "$INSTALL_TO_GENIE" = true ]; then
    install_skills_to_genie_workspace || exit 1
fi
