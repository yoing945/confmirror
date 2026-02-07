#!/bin/bash
# 功能: 【系统镜像备份】类JSON轻量规范配置驱动 → Git仓库同步，目录结构与系统完全一致
# 核心特性: ① 极致高效解析(无正则) ② 注释独占一行+块间必带逗号 ③ 书写灵活 ④ 自动判断文件/文件夹
# ⑤ parent-path父路径拼接 ⑥ 路径不存在自动跳过 ⑦ 日志前置+分级+轮转 ⑧ Git仓库1:1镜像系统目录

# ===================== 核心基础配置 =====================
SCRIPT_DIR=$(cd $(dirname $0); pwd)
GIT_BACKUP_ROOT="${SCRIPT_DIR}/backup"
GIT_BACKUP_SCRIPT_ROOT="${SCRIPT_DIR}/backup-script"
LOG_FILE="${SCRIPT_DIR}/log-backup.log"
CONF_FILE="${SCRIPT_DIR}/sync.conf"
export LANG=zh_CN.UTF-8
# 日志轮转配置：只保留最新的日志行数
LOG_KEEP_LINES=100

mkdir -p "${GIT_BACKUP_SCRIPT_ROOT}" 2>/dev/null

# ===================== 统一日志写入核心函数 =====================
# 参数: $1=日志级别(INFO/WARNING/ERROR), $2=日志消息, $3=终端颜色代码(32/33/31)
_write_log() {
  local level="$1"
  local msg="$2"
  local color="$3"
  local log_content="[$(date +'%Y-%m-%d %H:%M:%S')] [${level}] ${msg}"

  # 安全地将新日志插入文件顶部（兼容文件不存在）
  if [ -f "${LOG_FILE}" ]; then
    echo "${log_content}" | cat - "${LOG_FILE}" > "${LOG_FILE}.tmp"
  else
    echo "${log_content}" > "${LOG_FILE}.tmp"
  fi
  mv "${LOG_FILE}.tmp" "${LOG_FILE}"

  # 输出带颜色的终端日志
  echo -e "\033[${color}m${log_content}\033[0m"

  # 执行日志轮转
  _log_rotate
}

# 日志轮转（私有函数）
_log_rotate() {
  if [ -f "${LOG_FILE}" ]; then
    local line_count=$(wc -l < "${LOG_FILE}")
    if [ "${line_count}" -gt "${LOG_KEEP_LINES}" ]; then
      tail -n "${LOG_KEEP_LINES}" "${LOG_FILE}" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "${LOG_FILE}"
    fi
  fi
}

# ===================== 公共接口：分级日志函数 =====================
log_info() {
  _write_log "INFO" "$1" "32"
}

log_warning() {
  _write_log "WARNING" "$1" "33"
}

log_error() {
  _write_log "ERROR" "$1" "31"
}

# ===================== 帮助信息函数 =====================
show_help() {
  cat << EOF
系统配置镜像备份与还原工具

用法:
  sudo $0 [选项]

选项:
  (无参数)                执行默认的【系统配置备份】流程
  restore <路径>        还原指定文件或目录（如 /etc/apt/sources.list）
  restore-all           执行【全量还原】（需交互确认，高危操作！）
  help, -h, --help              显示此帮助信息

说明:
  • 配置文件: ${CONF_FILE}
  • 备份根目录: ${GIT_BACKUP_ROOT}
  • 日志文件: ${LOG_FILE}
  • 还原时自动从备份仓库映射原始路径
  • 目录还原仅同步备份中存在的内容，不会删除目标端额外文件

示例:
  # 备份所有配置
  sudo $0

  # 备份指定模块
  sudo $0 mod 'apt镜像源'

  # 还原单个文件
  sudo $0 restore /etc/hosts

  # 还原整个目录
  sudo $0 restore /etc/ssh/

  # 还原指定模块
  sudo $0 restore-mod 'apt镜像源'

  # 全量还原（谨慎！）
  sudo $0 restore-all

注意:
  必须使用 sudo 执行，否则因权限不足会失败。
EOF
}

backup_unit() {
  local full_path="$1"
  local module_name="$2"

  if [ ! -e "${full_path}" ]; then
    return 0
  fi

  # 如果是普通文件，直接备份 + 写 meta
  if [ -f "${full_path}" ]; then
    _backup_single_file "${full_path}" "${module_name}"
    return $?
  fi

  # 如果是目录，则递归处理每个子项
  if [ -d "${full_path}" ]; then
    log_info "[进入目录] ${full_path}"
    local entry
    while IFS= read -r -d '' entry; do
      # 跳过排除项（简单过滤，也可用更复杂的规则）
      case "$(basename "$entry")" in
        .git|*.log|*.tmp|cache|temp|*.pid|*.bak|downloads)
          log_info "[跳过排除项] $entry"
          continue
          ;;
      esac
      backup_unit "$entry" "${module_name}"  # 递归调用
    done < <(find "${full_path}" -mindepth 1 -print0 2>/dev/null)
    return 0
  fi

  log_warning "[跳过] 不支持的文件类型: ${full_path}"
  return 0
}

_backup_single_file() {
  local src_file="$1"
  local module_name="$2"
  local dest_file="${GIT_BACKUP_ROOT}${src_file}"
  local meta_file="${dest_file}.meta"

  # 获取元数据
  local mode=$(stat -c "%a" "${src_file}" 2>/dev/null || echo "644")
  local uid=$(stat -c "%u" "${src_file}" 2>/dev/null || echo "0")
  local gid=$(stat -c "%g" "${src_file}" 2>/dev/null || echo "0")

  # 确保目标父目录存在
  mkdir -p "$(dirname "${dest_file}")"

  # 复制文件（可用 cp 或 rsync，这里用 cp 更简单）
  if cp -f "${src_file}" "${dest_file}"; then
    # 写入 .meta
    cat > "${meta_file}" <<EOF
mode:${mode}
uid:${uid}
gid:${gid}
type:file
EOF
    log_info "[文件备份成功] ${module_name} → ${src_file} (权限:${mode} 用户:${uid}:${gid})"
  else
    log_error "[文件备份失败] ${src_file}"
  fi
}
# ===================== 新增：脚本执行备份核心私有函数 =====================
_backup_by_script() {
  local script_rel_path="$1"
  local module_name="$2"
  # 拼接脚本绝对路径
  local script_abs_path="${GIT_BACKUP_SCRIPT_ROOT}/${script_rel_path}"
  # 脚本不存在直接报错返回
  if [ ! -f "${script_abs_path}" ]; then
    log_error "[脚本备份失败] 模块${module_name} → 指定脚本不存在 ${script_abs_path}"
    return 1
  fi

  # 赋予脚本执行权限
  chmod +x "${script_abs_path}" >/dev/null 2>&1

  # ✅ 核心调整：入参只传1个！仅传入【操作类型 backup】，无其他冗余参数
  log_info "[脚本备份执行] 模块${module_name} → 运行脚本 ${script_abs_path}"
  if bash "${script_abs_path}" backup; then
    log_info "[脚本备份成功] 模块${module_name} → 脚本执行完成"
    return 0
  else
    log_error "[脚本备份失败] 模块${module_name} → 脚本执行返回非0状态码，执行异常！"
    return 1
  fi
}

# ===================== 新增：脚本执行还原核心私有函数 =====================
_restore_by_script() {
  local script_rel_path="$1"
  local module_name="$2"
  # 拼接脚本绝对路径 (配置文件同级目录)
  local script_abs_path="${GIT_BACKUP_SCRIPT_ROOT}/${script_rel_path}"

  # 脚本不存在直接报错返回
  if [ ! -f "${script_abs_path}" ]; then
    log_error "[脚本还原失败] 模块${module_name} → 指定脚本不存在 ${script_abs_path}"
    return 1
  fi

  # 赋予脚本执行权限
  chmod +x "${script_abs_path}" >/dev/null 2>&1

  # ✅ 核心调整：入参只传1个！仅传入【操作类型 restore】，无其他冗余参数
  log_info "[脚本还原执行] 模块${module_name} → 运行脚本 ${script_abs_path}"
  if bash "${script_abs_path}" restore; then
    log_info "[脚本还原成功] 模块${module_name} → 脚本执行完成"
    return 0
  else
    log_error "[脚本还原失败] 模块${module_name} → 脚本执行返回非0状态码，执行异常！"
    return 1
  fi
}

parse_conf_and_backup() {
  if [ ! -f "${CONF_FILE}" ]; then 
    log_warning "配置文件不存在: ${CONF_FILE}，跳过配置解析与备份流程！"
    return 0
  fi
  log_info "开始解析配置文件 → ${CONF_FILE}"

  # 1. 删除注释行（# 或 // 开头）
  # 2. 将所有换行符替换为空格，变成单行
  # 3. 在 { 和 } 周围加空格，便于分割
  local oneline=$(sed -e '/^\s*#/d' -e '/^\s*\/\//d' "${CONF_FILE}" | tr '\n' ' ' | sed 's/{/ { /g; s/}/ } /g')

  # 4. 使用 while 循环按单词读取，手动拼接 {...} 块
  local in_block=0
  local current_block=""
  local blocks=()

  for word in $oneline; do
    if [ "$word" = "{" ]; then
      in_block=1
      current_block=""
      continue
    elif [ "$word" = "}" ]; then
      if [ $in_block -eq 1 ]; then
        blocks+=("$current_block")
        in_block=0
        current_block=""
      fi
      continue
    fi

    if [ $in_block -eq 1 ]; then
      if [ -z "$current_block" ]; then
        current_block="$word"
      else
        current_block="$current_block $word"
      fi
    fi
  done

  # 5. 遍历所有提取出的块
  local block_count=0
  for block in "${blocks[@]}"; do
    block=$(echo "$block" | sed 's/^\s*//; s/\s*$//')
    [ -z "$block" ] && continue

    # ======== 新增：解析 script-path 脚本路径字段 ========
    local mod=$(echo "$block" | sed -n 's/.*mod\s*:\s*\([^,}[:space:]]*\).*/\1/p' | sed 's/^\s*//;s/\s*$//')
    local script_path=$(echo "$block" | sed -n 's/.*script-path\s*:\s*\([^,}[:space:]]*\).*/\1/p' | sed 's/^\s*//;s/\s*$//')
    local paths_str=$(echo "$block" | sed -n 's/.*paths\s*:\s*\[\([^]]*\)\].*/\1/p' | sed 's/^\s*//;s/\s*$//')
    local parent_path=$(echo "$block" | sed -n 's/.*parent-path\s*:\s*\([^,}[:space:]]*\).*/\1/p' | sed 's/^\s*//;s/\s*$//')

    if [ -z "$mod" ]; then
      log_warning "无效配置块，模块名为空 → 原始内容: $block"
      continue
    fi

    log_info "开始备份模块 → ${mod}"

    # ======== 核心改动：优先执行脚本备份，无脚本则走原路径备份 ========
    if [ -n "$script_path" ]; then
      _backup_by_script "${script_path}" "${mod}"
    else
      if [ -z "$paths_str" ]; then
        log_warning "无效配置块，模块${mod} 无script-path且paths为空 → 原始内容: $block"
        continue
      fi
      # 处理 paths 数组（原有逻辑不变）
      IFS=',' read -ra path_arr <<< "$(echo "$paths_str" | sed 's/\s*,\s*/,/g')"
      for sub_path in "${path_arr[@]}"; do
        sub_path=$(echo "$sub_path" | sed 's/^\s*//;s/\s*$//')
        [ -z "$sub_path" ] && continue

        local full_sync_path="$sub_path"
        if [ -n "$parent_path" ]; then
          full_sync_path="${parent_path}${sub_path}"
        fi

        backup_unit "$full_sync_path" "$mod"
      done
    fi

    block_count=$((block_count + 1))
  done

  if [ $block_count -eq 0 ]; then
    log_warning "未解析到任何有效配置块，请检查配置文件格式！"
  else
    log_info "成功解析 $block_count 个配置模块。"
  fi
}

# ===================== 备份指定模块（根据 mod 名称） =====================
backup_specific_module() {
  local target_mod="$1"

  if [ ! -f "${CONF_FILE}" ]; then 
    log_warning "配置文件不存在: ${CONF_FILE}，无法执行模块备份！"
    return 1
  fi

  log_info "正在查找模块 → '${target_mod}'"

  # 复用原有解析逻辑
  local oneline=$(sed -e '/^\s*#/d' -e '/^\s*\/\//d' "${CONF_FILE}" | tr '\n' ' ' | sed 's/{/ { /g; s/}/ } /g')
  local in_block=0
  local current_block=""
  local found=0

  for word in $oneline; do
    if [ "$word" = "{" ]; then
      in_block=1
      current_block=""
      continue
    elif [ "$word" = "}" ]; then
      if [ $in_block -eq 1 ]; then
        # 提取 mod 字段
        local mod=$(echo "$current_block" | sed -n 's/.*mod\s*:\s*\([^,}[:space:]]*\).*/\1/p' | sed 's/^\s*//;s/\s*$//')
        if [ "$mod" = "$target_mod" ]; then
            found=1
            # ======== 新增：解析 script-path 字段 ========
            local paths_str=$(echo "$current_block" | sed -n 's/.*paths\s*:\s*\[\([^]]*\)\].*/\1/p' | sed 's/^\s*//;s/\s*$//')
            local parent_path=$(echo "$current_block" | sed -n 's/.*parent-path\s*:\s*\([^,}[:space:]]*\).*/\1/p' | sed 's/^\s*//;s/\s*$//')
            local script_path=$(echo "$current_block" | sed -n 's/.*script-path\s*:\s*\([^,}[:space:]]*\).*/\1/p' | sed 's/^\s*//;s/\s*$//')

            log_info "→ 匹配到模块: ${mod}"
            # ======== 核心改动：优先执行脚本备份 ========
            if [ -n "$script_path" ]; then
              _backup_by_script "${script_path}" "${mod}"
            else
              if [ -z "$paths_str" ]; then
                log_warning "模块 '${mod}' 的 paths 为空，跳过"
                break
              fi
              IFS=',' read -ra path_arr <<< "$(echo "$paths_str" | sed 's/\s*,\s*/,/g')"
              for sub_path in "${path_arr[@]}"; do
                sub_path=$(echo "$sub_path" | sed 's/^\s*//;s/\s*$//')
                [ -z "$sub_path" ] && continue
                local full_sync_path="$sub_path"
                [ -n "$parent_path" ] && full_sync_path="${parent_path}${sub_path}"
                backup_unit "$full_sync_path" "$mod"
              done
            fi
            break
        fi
        in_block=0
        current_block=""
      fi
      continue
    fi

    if [ $in_block -eq 1 ]; then
      if [ -z "$current_block" ]; then
        current_block="$word"
      else
        current_block="$current_block $word"
      fi
    fi
  done

  if [ $found -eq 0 ]; then
    log_error "未找到模块名称为 '${target_mod}' 的配置项！"
    log_info "可用模块列表（来自 ${CONF_FILE}）："
    sed -n 's/.*mod\s*:\s*\([^,}[:space:]]*\).*/  - \1/p' "${CONF_FILE}" | grep -v '^\s*$' | sort -u | while read line; do
      echo "$line"
    done
    return 1
  fi
}

# ===================== Git推送函数【适配分级日志】 =====================
git_push_backup(){
  cd "${GIT_BACKUP_ROOT}"
  git add .
  git commit -m "[$(date +'%Y-%m-%d %H:%M:%S')] 自动备份服务配置文件" >/dev/null 2>&1
  git push origin main
  [ $? -eq 0 ] && log_info "Git仓库已自动提交并推送至远端！" || log_warning "Git推送完成/无变更，无需重复推送"
}

# ===================== 还原单个文件或目录【安全模式：目录不删除目标端多余文件】 =====================
restore_unit() {
  local original_path="$1"
  local backup_path="${GIT_BACKUP_ROOT}${original_path}"
  local meta_file="${backup_path}.meta"
  
  # ========== 严格依赖 .meta 存在 ==========
  if [ ! -f "${meta_file}" ]; then
    log_warning "[还原跳过] 缺少元数据文件（.meta），无法安全还原 → ${original_path}"
    return 0
  fi

  # 检查备份内容是否存在（虽然有 .meta 通常意味着有内容，但双重保险）
  if [ ! -e "${backup_path}" ]; then
    log_warning "[还原跳过] 备份内容不存在（仅有 .meta？）→ ${original_path}"
    return 0
  fi

  # 读取元数据（现在可以确信文件存在）
  local mode="644"
  local uid="0"
  local gid="0"
  local ftype="unknown"

  while IFS=':' read -r key value; do
    case "$key" in
      mode) mode="$value" ;;
      uid)  uid="$value" ;;
      gid)  gid="$value" ;;
      type) ftype="$value" ;;
    esac
  done < "${meta_file}"

  log_info "[元数据加载] 类型:${ftype} 权限:${mode} 用户:${uid}:${gid} → ${original_path}"

  # 确保目标父目录存在
  mkdir -p "$(dirname "${original_path}")"

  if [ "$ftype" = "file" ] && [ -f "${backup_path}" ]; then
    if cp -f "${backup_path}" "${original_path}" &&
       chmod "${mode}" "${original_path}" &&
       chown "${uid}:${gid}" "${original_path}"; then
      log_info "[文件还原成功] ${original_path}"
    else
      log_error "[文件还原失败] ${original_path}"
    fi

  elif [ "$ftype" = "dir" ] && [ -d "${backup_path}" ]; then
    mkdir -p "${original_path}"
    # 同步内容，排除 .meta 和其他临时文件
    if rsync -avz --exclude=".git" --exclude="*.log" --exclude="*.tmp" \
              --exclude="cache" --exclude="temp" --exclude="*.pid" \
              --exclude="*.bak" --exclude="downloads" \
              --exclude="*.meta" \
              "${backup_path}/" "${original_path}/" &&
       chmod "${mode}" "${original_path}" &&
       chown "${uid}:${gid}" "${original_path}"; then
      log_info "[目录还原成功] ${original_path}"
    else
      log_error "[目录还原失败] ${original_path}"
    fi

  else
    log_error "[类型不匹配] .meta 声明类型为 ${ftype}，但实际备份内容不符 → ${original_path}"
  fi
}

# ===================== 还原指定模块（根据 mod 名称） =====================
restore_specific_module() {
  local target_mod="$1"

  if [ ! -f "${CONF_FILE}" ]; then 
    log_warning "配置文件不存在: ${CONF_FILE}，无法执行模块还原！"
    return 1
  fi

  log_info "正在查找模块 → '${target_mod}'"

  # 复用原有解析逻辑
  local oneline=$(sed -e '/^\s*#/d' -e '/^\s*\/\//d' "${CONF_FILE}" | tr '\n' ' ' | sed 's/{/ { /g; s/}/ } /g')
  local in_block=0
  local current_block=""
  local found=0

  for word in $oneline; do
    if [ "$word" = "{" ]; then
      in_block=1
      current_block=""
      continue
    elif [ "$word" = "}" ]; then
      if [ $in_block -eq 1 ]; then
        # 提取 mod 字段
        local mod=$(echo "$current_block" | sed -n 's/.*mod\s*:\s*\([^,}[:space:]]*\).*/\1/p' | sed 's/^\s*//;s/\s*$//')
        if [ "$mod" = "$target_mod" ]; then
            found=1
            local paths_str=$(echo "$current_block" | sed -n 's/.*paths\s*:\s*\[\([^]]*\)\].*/\1/p' | sed 's/^\s*//;s/\s*$//')
            local parent_path=$(echo "$current_block" | sed -n 's/.*parent-path\s*:\s*\([^,}[:space:]]*\).*/\1/p' | sed 's/^\s*//;s/\s*$//')
            # ======== 新增：解析 script-path 字段 ========
            local script_path=$(echo "$current_block" | sed -n 's/.*script-path\s*:\s*\([^,}[:space:]]*\).*/\1/p' | sed 's/^\s*//;s/\s*$//')

            log_info "→ 匹配到模块: ${mod}，开始还原其所有路径/脚本..."
            # ======== 核心改动：优先执行脚本还原 ========
            if [ -n "$script_path" ]; then
              _restore_by_script "${script_path}" "${mod}"
            else
              if [ -z "$paths_str" ]; then
                log_warning "模块 '${mod}' 的 paths 为空，跳过还原"
                break
              fi
              local clean_paths=$(echo "$paths_str" | sed 's/^\s*//; s/\s*$//; s/\s*,\s*/,/g')
              IFS=',' read -ra path_arr <<< "$clean_paths"
              #IFS=',' read -ra path_arr <<< "$(echo "$paths_str" | sed 's/.*,\s*/,/g')"
              for sub_path in "${path_arr[@]}"; do
                sub_path=$(echo "$sub_path" | sed 's/^\s*//;s/\s*$//')
                [ -z "$sub_path" ] && continue
                local full_sync_path="$sub_path"
                [ -n "$parent_path" ] && full_sync_path="${parent_path}${sub_path}"
                restore_unit "$full_sync_path"
              done
            fi
            break
        fi
        in_block=0
        current_block=""
      fi
      continue
    fi

    if [ $in_block -eq 1 ]; then
      if [ -z "$current_block" ]; then
        current_block="$word"
      else
        current_block="$current_block $word"
      fi
    fi
  done

  if [ $found -eq 0 ]; then
    log_error "未找到模块名称为 '${target_mod}' 的配置项！"
    log_info "可用模块列表（来自 ${CONF_FILE}）："
    sed -n 's/.*mod\s*:\s*\([^,}[:space:]]*\).*/  - \1/p' "${CONF_FILE}" | grep -v '^\s*$' | sort -u | while read line; do
      echo "$line"
    done
    return 1
  fi
}

# ===================== 全量还原（危险操作）=====================
restore_all() {
  log_warning "⚠️  警告：即将执行【全量系统配置还原】！此操作会覆盖当前系统中的配置文件。"
  log_warning "⚠️  所有被备份的文件/目录将从 Git 备份仓库还原至原始位置。"
  read -p "是否继续？(输入 YES 确认): " confirm
  if [ "$confirm" != "YES" ]; then
    log_info "用户取消全量还原操作。"
    return 0
  fi

  log_info "开始全量还原所有备份模块..."

  # 重新解析配置文件，遍历所有 paths
  local oneline=$(sed -e '/^\s*#/d' -e '/^\s*\/\//d' "${CONF_FILE}" | tr '\n' ' ' | sed 's/{/ { /g; s/}/ } /g')
  local in_block=0
  local current_block=""
  local blocks=()

  for word in $oneline; do
    if [ "$word" = "{" ]; then
      in_block=1; current_block=""; continue
    elif [ "$word" = "}" ]; then
      if [ $in_block -eq 1 ]; then blocks+=("$current_block"); in_block=0; fi
      continue
    fi
    [ $in_block -eq 1 ] && current_block="$current_block $word"
  done

  for block in "${blocks[@]}"; do
    block=$(echo "$block" | sed 's/^\s*//; s/\s*$//')
    [ -z "$block" ] && continue

    # ======== 新增：解析 script-path 字段 ========
    local mod=$(echo "$block" | sed -n 's/.*mod\s*:\s*\([^,}[:space:]]*\).*/\1/p' | sed 's/^\s*//;s/\s*$//')
    local paths_str=$(echo "$block" | sed -n 's/.*paths\s*:\s*\[\([^]]*\)\].*/\1/p' | sed 's/^\s*//;s/\s*$//')
    local parent_path=$(echo "$block" | sed -n 's/.*parent-path\s*:\s*\([^,}[:space:]]*\).*/\1/p' | sed 's/^\s*//;s/\s*$//')
    local script_path=$(echo "$block" | sed -n 's/.*script-path\s*:\s*\([^,}[:space:]]*\).*/\1/p' | sed 's/^\s*//;s/\s*$//')

    if [ -z "$mod" ]; then continue; fi

    log_info "→ 还原模块: ${mod}"
    # ======== 核心改动：优先执行脚本还原 ========
    if [ -n "$script_path" ]; then
      _restore_by_script "${script_path}" "${mod}"
    else
      if [ -z "$paths_str" ]; then continue; fi
      IFS=',' read -ra path_arr <<< "$(echo "$paths_str" | sed 's/.*,\s*/,/g')"
      for sub_path in "${path_arr[@]}"; do
        sub_path=$(echo "$sub_path" | sed 's/^\s*//;s/\s*$//')
        [ -z "$sub_path" ] && continue
        local full_path="$sub_path"
        [ -n "$parent_path" ] && full_path="${parent_path}${sub_path}"
        restore_unit "$full_path"
      done
    fi
  done

  log_info "✅ 全量还原操作完成！"
}

# ===================== 主调度函数（子命令模式） =====================
main() {
  # 确保以 root 运行（但 help/补全可非 root）
  if [ "$EUID" -ne 0 ] && [[ "$1" != "help" ]] && [[ "$1" != "" ]]; then
    echo "错误: 必须使用 sudo 执行此脚本（help 除外）！" >&2
    echo "用法: sudo $0 <command> [args] 或 $0 help" >&2
    exit 1
  fi

  # 创建日志目录（保险）
  mkdir -p "${SCRIPT_DIR}" 2>/dev/null

  local cmd="$1"
  shift 2>/dev/null || true  # 移除第一个参数，方便后续处理

  case "${cmd}" in
    ""|"backup")
      log_info "================================ 开始系统配置镜像备份 =================================="
      # === 新增：宽松二次确认 ===
      read -p "即将执行【全量配置备份】，是否继续？(Y/n，默认 Y): " confirm_backup
      case "${confirm_backup,,}" in
        n|no)
          log_info "用户取消全量备份操作。"
          exit 0
          ;;
        *) # 默认继续
          ;;
      esac
      parse_conf_and_backup
      log_info "✅ 所有配置模块镜像备份流程执行完成！"
      # git_push_backup  # 如需自动推送可取消注释
      ;;

    "mod")
      if [ $# -eq 0 ]; then
        log_error "mod 命令需要指定模块名，例如：mod 'apt镜像源'"
        echo "请使用 help 查看详细帮助"
        exit 1
      fi
      local target_mod="$1"
      log_info "================================ 开始备份指定模块: ${target_mod} =================================="
      backup_specific_module "${target_mod}"
      log_info "✅ 模块 '${target_mod}' 备份完成！"
      ;;

    "restore")
      if [ $# -eq 0 ]; then
        log_error "restore 需要指定路径，例如：restore /etc/apt/sources.list"
        echo "请使用 help 查看详细帮助"
        exit 1
      fi
      log_info "================================ 开始指定路径还原 =================================="
      restore_unit "$1"
      log_info "✅ 指定路径还原完成！"
      ;;

    "restore-mod")
      if [ "$#" -eq 0 ]; then
        log_error "restore-mod 需要指定模块名，例如：restore-mod 'apt镜像源'"
        echo "请使用 help 查看详细帮助"
        exit 1
      fi
      local target_mod="$1"
      log_info "================================ 开始还原指定模块: ${target_mod} =================================="
      restore_specific_module "${target_mod}"
      log_info "✅ 模块 '${target_mod}' 还原完成！"
      ;;

    "restore-all")
      log_info "================================ 开始全量还原流程 =================================="
      restore_all
      ;;

    "help"|"-h"|"--help")
      show_help
      exit 0
      ;;

    *)
      log_error "未知命令: ${cmd}"
      echo "请使用 help 查看详细帮助"
      exit 1
      ;;
  esac
}

# ===================== 脚本入口 =====================
# 注意：此时 log_* 函数已定义，可以安全使用
main "$@"