# План безопасной очистки веток

Пользователь явно разрешил merge в одну ветку и удаление остальных 11 октября2026. Итоговая поддерживаемая ветка — master. Ниже исходный аудит: рекомендации KEEP до согласования заменены этим разрешением. Перед удалением фиксируются recovery tags и проверяются remote tips. Worktrees, файлы, patch и данные не удаляются.

| Ветка | Зафиксированный tip | Что интегрируется / остаётся | Recovery ref | Рекомендация и безопасность |
|---|---|---|---|---|
| master / origin/master | f6c6c7c80558f9c451ef0307a62c430dbf0c8456 (local master565c720) | Default; P1 выборочно, unsafe storage/operator/SIM остаются историческими источниками | recovery/2026-10-11/master | KEEP, никогда не удалять default |
| frontend-test-brach / origin/frontend-test-brach | 8bdec6c9b404555d9b8197ff48789f554b73faec | Approved interface — integration base | recovery/2026-10-11/frontend | KEEP до merge и точного согласования local/remote deletion |
| backend-antidrop-postgres (local) | 0fb475f813d547749562837f4a3d57db9b4bb715 | Backend/DB/domain/tests/docs выборочно; frontend прежний не переносится | recovery/2026-10-11/backend | ARCHIVE CANDIDATE; связан с worktree, deletion сейчас запрещён |
| origin/zima | 19162eca333bfc05ddfbfe642675b87a53076d47 | P1 compatible parts; operator требует последующей адаптации, исторические reports не актуальные metrics | recovery/2026-10-11/zima | KEEP источник уникальной отложенной функции, не объявлять safe delete |
| origin/my-branch | 11d78b20d4935264603e873f1851c8a537754554 | История уже в master; storage заменён более безопасным, полезные требования сохранены | recovery/2026-10-11/my-branch | ARCHIVE CANDIDATE; exact remote deletion только после отдельного review |
| feature/learning-server (local) | b032ae4d96c151d8d9b7f8cc646e60de6bc7827b | Новый учебный backend/PDF import, выборочно перенесён | исходная ветка/worktree сохранены | KEEP до финального merge и recovery tag |
| feature/learning-cards (local) | 680602366a0d2dc09c4e6e0c09aba6c36d72d21e | Учебный frontend/CI browser config, выборочно перенесён; root BFF edits в worktree | исходная ветка/worktree сохранены | KEEP; незакоммиченные BFF edits в feature worktree запрещают удаление |
| integration/antidrop-unified | см. текущий git rev-parse HEAD / PR | Release candidate; ещё не approved merge | reviewable commits / PR | KEEP активная review ветка |

При первоначальном аудите recovery tags были локальными; перед cleanup они опубликованы (см. Completed cleanup). Они защищают commits, а не незакоммиченные файлы. Нельзя удалять ветку только по ancestry/merged flag: проверить сохранённое поведение и deferred operator. Не удалять worktrees, patch, tags или volumes в рамках branch cleanup. При изменившемся tip операцию исключить и сообщить владельцу.

## Authorized final cleanup

Keep local/remote master only. Archive all source tips under recovery/2026-10-11/*, including learning-cards, learning-server and unified. Publish recovery tags before deleting remote branches. Detach linked worktrees before deleting their local branches; keep their files and any uncommitted changes. Recheck remote tip SHAs; do not delete a branch whose tip changed unexpectedly. Archive tags preserve deferred operator sources and historical layouts. No force push, worktree deletion or volume deletion.

## Completed cleanup — 2026-10-11

Published master74bcc2b by fast-forward push. Published all8 recovery tags, then checked source tips against the audit. Deleted remote frontend-test-brach@8bdec6c, my-branch@11d78b2 and zima@19162ec in one atomic push. Deleted local backend-antidrop-postgres@0fb475f, feature/learning-cards@6806023, feature/learning-server@b032ae4, frontend-test-brach@8bdec6c and integration/antidrop-unified@74bcc2b after detaching their worktrees. `git branch -a` and remote refs confirm master is the sole branch.

All worktree directories and local data remain. Dirty learning frontend files were byte-compared with the unified implementation and matched; the older generator change in learning-server is included in the newer unified generator. Their on-disk copies remain intact. Original untracked inventory was preserved as `.local/BRANCH_INVENTORY.pre-integration.md` before switching the primary directory to master. No force push or data deletion.

Tags: `recovery/2026-10-11/{backend,frontend,learning-cards,learning-server,master,my-branch,unified,zima}`. Inspect with `git show <tag>:<path>` or restore to a separate worktree from a tag. These are archival tags, not additional maintained branches.
