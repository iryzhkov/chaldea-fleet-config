-- Real attachment and diagnostic smoke for every selected server.
local root = assert(vim.env.HUYANG_TOOLCHAIN_SMOKE_ROOT)
assert(root:find("chaldea%-scratch/agent%-tooling"), "scratch projects required")
local cfg = vim.g.huyang_fleet_config
local cases = {
  go = { "main.go", "package main\nvar broken int = \"bad\"\nfunc main() {}\n",
    { ["go.mod"] = "module example.com/probe\n\ngo 1.27\n" } },
  rust = { "src/main.rs", "fn main() { let broken: i32 = \"bad\"; }\n",
    { ["Cargo.toml"] = '[package]\nname="probe"\nversion="0.1.0"\nedition="2021"\n' } },
  python = { "main.py", 'broken: int = "bad"\n', {} },
  typescript = { "main.ts", 'const broken: number = "bad"; export { broken };\n',
    { ["tsconfig.json"] = '{"compilerOptions":{"strict":true}}\n',
      ["package.json"] = '{"name":"probe","version":"1.0.0"}\n' } },
  javascript = { "main.js", '// @ts-check\n/** @type {number} */\nconst broken = "bad"; export { broken };\n',
    { ["package.json"] = '{"name":"probe","version":"1.0.0"}\n' } },
  java = { "src/main/java/probe/Main.java", 'package probe;\npublic class Main { int broken = "bad"; }\n',
    { ["pom.xml"] = "<project><modelVersion>4.0.0</modelVersion><groupId>probe</groupId><artifactId>probe</artifactId><version>1</version><properties><maven.compiler.source>21</maven.compiler.source><maven.compiler.target>21</maven.compiler.target></properties></project>\n" } },
  cpp = { "main.cpp", 'int broken = "bad";\n', { ["compile_flags.txt"] = "-std=c++17\n" } },
  c = { "main.c", 'int broken = "bad";\n', {} },
  bash = { "main.sh", "#!/usr/bin/env bash\necho $undefined_variable\n", {} },
}
local function write(path, text)
  vim.fn.mkdir(vim.fs.dirname(path), "p")
  local f = assert(io.open(path, "w"))
  f:write(text)
  f:close()
end
local ok, err = pcall(function()
  for _, language in ipairs(cfg.languages) do
    local case = assert(cases[language])
    local project = root .. "/" .. language
    for path, text in pairs(case[3]) do write(project .. "/" .. path, text) end
    local path = project .. "/" .. case[1]
    write(path, case[2])
    vim.cmd.cd(project)
    vim.cmd.edit(vim.fn.fnameescape(path))
    local bufnr = vim.api.nvim_get_current_buf()
    local ft = cfg.servers[language].filetype
    vim.bo[bufnr].filetype = ft
    assert(vim.treesitter.get_parser(bufnr):parse(), "parser failed " .. language)
    local attached = vim.wait(180000, function()
      for _, client in ipairs(vim.lsp.get_clients({ bufnr = bufnr })) do
        if client.name == cfg.servers[language].config and client.initialized then return true end
      end
      return false
    end, 100)
    assert(attached, "server did not attach: " .. language)
    vim.cmd("silent write")
    local diagnostic = vim.wait(180000, function()
      for _, item in ipairs(vim.diagnostic.get(bufnr)) do
        if item.severity == vim.diagnostic.severity.ERROR
          or (language == "bash" and tostring(item.code):find("2154", 1, true)) then return true end
      end
      return false
    end, 100)
    assert(diagnostic, "server published no expected diagnostic: " .. language)
    print("HUYANG_TOOLCHAIN_SMOKE " .. language .. " attached and diagnosed")
    for _, client in ipairs(vim.lsp.get_clients({ bufnr = bufnr })) do client:stop(true) end
    vim.cmd.bwipeout({ bang = true })
  end
end)
if not ok then
  io.stderr:write(tostring(err) .. "\n")
  vim.cmd("cquit 1")
end
vim.cmd("qa!")
