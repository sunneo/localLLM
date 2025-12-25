#!/bin/bash
export SCRIPT_ROOT=$(realpath `dirname "${BASH_SOURCE}"`)
script_name=$( basename ${0#-} ) #- needed if sourced no path
this_script=$( basename ${BASH_SOURCE} )
export CURRENT_AI_CHATID=""
function get_chat_dir {
   local chatid="$1"
   local path="user_profiles/$USER/${chatid}"
   echo "$path"
}
function create_subchat {
   local timestamp=`date +%s`
   local path="user_profiles/$USER/${timestamp}"
   mkdir -p user_profiles
   chmod 777 user_profiles
   mkdir -p "${path}"
   local orig_llama_bin=`realpath llama.bin`
   local orig_rag_data=`realpath rag_data`
   local orig_models=`realpath models`
   local orig_llm_call_tool=`realpath llm_call_tools`
   local orig_addons=`realpath addons`
   local orig_chatcall_py=`realpath chatcall.py`
   local orig_ai_config_common_py=`realpath ai_config_common.py`
   local orig_ai_config_py=`realpath ai_config.py`
   local orig_create_sub_chat_sh=`realpath create-sub-chat.sh`

   pushd "${path}" >/dev/null 2>&1
   if [ ! -e "llama.bin" ]; then
      ln -s "${orig_llama_bin}" llama.bin
   fi
   if [ ! -e "models" ]; then
      ln -s "${orig_models}" models
   fi
   if [ ! -e "rag_data" ]; then
      ln -s "${orig_rag_data}" rag_data
   fi

   if [ ! -e "llm_call_tool" ]; then
      ln -s "${orig_llm_call_tool}" llm_call_tool
   fi
   if [ ! -e "addons" ]; then
      ln -s "${orig_addons}" addons
   fi
   if [ ! -e "chatcall.py" ]; then
      ln -s "${orig_chatcall_py}" chatcall.py
   fi
   if [ ! -e "ai_config_common.py" ]; then
      ln -s "${orig_ai_config_common_py}" ai_config_common.py
   fi
   if [ ! -e "ai_config.py" ]; then
      ln -s "${orig_ai_config_py}" ai_config.py
   fi
   if [ ! -e "override_ai_config.py" ]; then
      cp "${orig_ai_config_py}" override_ai_config.py
   fi
   if [ ! -e "create-sub-chat.sh" ]; then
      ln -s "${orig_create_sub_chat_sh}" "create-sub-chat.sh"
   fi
   popd >/dev/null 2>&1
   echo "${path}"
}
function start_new_chat {
   local chatid="$1"
   if [ ! -e `get_chat_dir "$1"` ]; then
      echo "Run create_subchat first"
      return -1
   fi
   cd "`get_chat_dir ${chatid}`"
   export CURRENT_AI_CHATID="${chatid}"
   mkdir -p .info
   echo "${chatid}" > .info/chatid
   
   return 0
}
function chat {
   if [ "${CURRENT_AI_CHATID}" == "" ]; then
      if [ ! -e .info/chatid ]; then
         echo "start_new_chat first"
         return -1
      fi
      CURRENT_AI_CHATID=`cat .info/chatid | tr -d "\n"`
   fi
   python3 chatcall.py $@
}

function _start_new_chat_complete {
   local cur=${COMP_WORDS[COMP_CWORD]}
   local userdir="user_profiles/${USER}"
   if [ ! -e "{userdir}" ]; then
      mkdir -p "${userdir}"
   fi
   COMPREPLY=( $(compgen -W `ls ${userdir}` -- $cur) )
   return 0
}

function print_usage {
   local usage=`cat << EOL
   ${this_script} create_subchat : create sub chat 
      create a sub chat
      returns new chat id
   ${this_script} start_new_chat <chat_id>
      start a created chat
   * after started a new chat:
      ${this_script} chat <messages>

EOL
`
   echo "${usage}"

   return 0
}

function _main_complete {
   local cur=${COMP_WORDS[COMP_CWORD]}
   COMPREPLY=( $(compgen -W "create_subchat start_new_chat chat" -- $cur) )
   return 0
}

function main {
   case "$1" in 
   "create_subchat")
      create_subchat
      ;;
   "start_new_chat")
      start_new_chat "$2"
      ;;
   "chat")
      chat "$2"
      ;;

   *)
      print_usage
      complete -F _main_complete ./${this_script}
      ;;
   esac

   return 0
}
if [ "${script_name}" == "${this_script}" ] ; then
   main $@
else
   complete -F _start_new_chat_complete start_new_chat
   complete -F _main_complete ./${this_script}

fi 

