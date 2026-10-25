/* Living Universe read-only observer v0.3.
 * Not a kernel, sandbox, general HTTP server, or production remote service.
 * Loopback only. One pre-opened HTML file; optionally one explicitly selected log.
 * No execution/write endpoints, subprocesses, path resolution, or directory serving.
 */
#include <stdint.h>
#include <stddef.h>

#define WEB_MAX (4U*1024U*1024U)
#define LOG_MAX (128U*1024U)
#define RESPONSE_MAX (LOG_MAX*6U+4096U)
static char request_buffer[8192], response_buffer[RESPONSE_MAX], serial_buffer[LOG_MAX+1];
static char token[65], expected_host[80], expected_origin[96];
static uint64_t started, requests;
static unsigned port = 8765;
static unsigned char *web_data;
static size_t web_size;
static int have_log;
static int failed_buffer;
static size_t response_used;

static size_t slen(const char *s) { size_t n=0; while(s[n]) ++n; return n; }
static int eq(const char *a,const char *b) { while(*a && *a==*b) {++a;++b;} return *a==*b; }
static char lower(char c) { return c>='A'&&c<='Z'?(char)(c+32):c; }
static int ieq(const char *a,const char *b) { while(*a&&lower(*a)==lower(*b)){++a;++b;}return *a==*b; }
void *memcpy(void *dst,const void *src,size_t n) { unsigned char *d=dst;const unsigned char*s=src;for(size_t i=0;i<n;i++)d[i]=s[i];return dst; }
void *memset(void *dst,int v,size_t n) { unsigned char*d=dst;for(size_t i=0;i<n;i++)d[i]=(unsigned char)v;return dst; }
static void copy(char *d,size_t cap,const char *s) { size_t n=slen(s);if(n>=cap)n=cap-1;memcpy(d,s,n);d[n]=0; }
static void append(char *d,size_t cap,const char *s) { size_t n=d==response_buffer?response_used:slen(d),m=slen(s);if(n+m>=cap){failed_buffer=1;return;}memcpy(d+n,s,m+1);if(d==response_buffer)response_used=n+m; }
static void number(char *d,size_t cap,uint64_t value) { char b[32];size_t n=0;do{b[n++]=(char)('0'+value%10);value/=10;}while(value);while(n){char x[2]={b[--n],0};append(d,cap,x);} }
static int constant_equal(const char *a,const char *b) { if(slen(a)!=64||slen(b)!=64)return 0;unsigned d=0;for(unsigned i=0;i<64;i++)d|=(unsigned char)a[i]^(unsigned char)b[i];return d==0; }
static void json_string(char*d,size_t cap,const unsigned char*s,size_t n) { const char *hex="0123456789abcdef";append(d,cap,"\"");for(size_t i=0;i<n;i++){unsigned c=s[i];if(c=='"')append(d,cap,"\\\"");else if(c=='\\')append(d,cap,"\\\\");else if(c<32||c>=127){char b[7]={'\\','u','0','0',hex[c>>4],hex[c&15],0};append(d,cap,b);}else{char b[2]={(char)c,0};append(d,cap,b);}}append(d,cap,"\""); }

#ifdef _WIN32
/* Minimal ABI declarations keep this hosted utility buildable without an SDK or CRT.
 * API declarations are intentionally restricted; native kernel sources do not use these.
 */
#define DLL __declspec(dllimport)
typedef void *HANDLE;
typedef uintptr_t SOCKET;
typedef uint32_t DWORD;
typedef int32_t BOOL;
typedef uint16_t WCHAR;
typedef struct { uint32_t low,high; } FILETIME_LU;
typedef struct { DWORD attributes; FILETIME_LU create,access,write; DWORD volume,sizeHigh,sizeLow,links,indexHigh,indexLow; } FILEINFO_LU;
DLL HANDLE __stdcall GetStdHandle(DWORD);
DLL BOOL __stdcall WriteFile(HANDLE,const void*,DWORD,DWORD*,void*);
DLL HANDLE __stdcall GetProcessHeap(void);
DLL void* __stdcall HeapAlloc(HANDLE,DWORD,size_t);
DLL BOOL __stdcall HeapFree(HANDLE,DWORD,void*);
DLL uint64_t __stdcall GetTickCount64(void);
DLL HANDLE __stdcall GetCurrentProcess(void);
DLL BOOL __stdcall GetProcessTimes(HANDLE,FILETIME_LU*,FILETIME_LU*,FILETIME_LU*,FILETIME_LU*);
DLL HANDLE __stdcall CreateFileW(const WCHAR*,DWORD,DWORD,void*,DWORD,DWORD,HANDLE);
DLL BOOL __stdcall ReadFile(HANDLE,void*,DWORD,DWORD*,void*);
DLL BOOL __stdcall SetFilePointerEx(HANDLE,int64_t,int64_t*,DWORD);
DLL BOOL __stdcall GetFileSizeEx(HANDLE,int64_t*);
DLL DWORD __stdcall GetFileType(HANDLE);
DLL BOOL __stdcall GetFileInformationByHandle(HANDLE,FILEINFO_LU*);
DLL BOOL __stdcall CloseHandle(HANDLE);
DLL int __stdcall MultiByteToWideChar(unsigned,DWORD,const char*,int,WCHAR*,int);
DLL int __stdcall WideCharToMultiByte(unsigned,DWORD,const WCHAR*,int,char*,int,const char*,BOOL*);
DLL WCHAR* __stdcall GetCommandLineW(void);
DLL WCHAR** __stdcall CommandLineToArgvW(const WCHAR*,int*);
DLL HANDLE __stdcall LocalFree(HANDLE);
DLL void __stdcall ExitProcess(unsigned);
DLL int32_t __stdcall BCryptGenRandom(void*,unsigned char*,unsigned long,unsigned long);
DLL int __stdcall WSAStartup(uint16_t,void*);
DLL int __stdcall WSACleanup(void);
DLL SOCKET __stdcall socket(int,int,int);
DLL int __stdcall bind(SOCKET,const void*,int);
DLL int __stdcall listen(SOCKET,int);
DLL SOCKET __stdcall accept(SOCKET,void*,int*);
DLL int __stdcall recv(SOCKET,char*,int,int);
DLL int __stdcall send(SOCKET,const char*,int,int);
DLL int __stdcall setsockopt(SOCKET,int,int,const char*,int);
DLL int __stdcall closesocket(SOCKET);
#define BAD_SOCKET ((SOCKET)~(uintptr_t)0)
#define BAD_FILE ((HANDLE)(intptr_t)-1)
typedef HANDLE FILE_HANDLE;
static FILE_HANDLE log_handle;
static void output(const char *s) { DWORD written; WriteFile(GetStdHandle((DWORD)-11),s,(DWORD)slen(s),&written,0); }
static uint64_t now_ms(void) { return GetTickCount64(); }
static void *allocate(size_t n) { return HeapAlloc(GetProcessHeap(),0,n); }
static void release(void*p) { if(p)HeapFree(GetProcessHeap(),0,p); }
static int random_bytes(unsigned char*b,size_t n) { return BCryptGenRandom(0,b,(DWORD)n,2)==0; }
static FILE_HANDLE open_file(const char *path) {
 static WCHAR wide[2048];if(!MultiByteToWideChar(65001,8,path,-1,wide,2048))return BAD_FILE;
 HANDLE h=CreateFileW(wide,0x80000000U,7,0,3,0x00200000U,0);if(h==BAD_FILE)return h;
 FILEINFO_LU info;if(GetFileType(h)!=1||!GetFileInformationByHandle(h,&info)||(info.attributes&(0x10|0x400))){CloseHandle(h);return BAD_FILE;}return h;
}
static uint64_t file_size(FILE_HANDLE h) { int64_t n=0;if(!GetFileSizeEx(h,&n)||n<0)return UINT64_MAX;return(uint64_t)n; }
static int read_at(FILE_HANDLE h,void*b,size_t n,uint64_t offset) { DWORD read=0;if(offset>INT64_MAX||!SetFilePointerEx(h,(int64_t)offset,0,0)||!ReadFile(h,b,(DWORD)n,&read,0))return-1;return(int)read; }
static void close_file(FILE_HANDLE h) { CloseHandle(h); }
static void close_socket(SOCKET s) { closesocket(s); }
static void socket_timeout(SOCKET s) { DWORD n=1000;setsockopt(s,0xffff,0x1006,(const char*)&n,sizeof(n));setsockopt(s,0xffff,0x1005,(const char*)&n,sizeof(n)); }
static uint64_t cpu_ms(void) { FILETIME_LU c,e,k,u;if(!GetProcessTimes(GetCurrentProcess(),&c,&e,&k,&u))return 0;return((((uint64_t)k.high<<32)|k.low)+(((uint64_t)u.high<<32)|u.low))/10000; }
static uint64_t peak_rss_bytes(void) { return 0; }
static const char *os_name(void) { return "Windows"; }
static int socket_init(void) { unsigned char wsa[512];return WSAStartup(0x0202,wsa)==0; }
#else
#define _POSIX_C_SOURCE 200809L
#include <unistd.h>
#include <stdlib.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/time.h>
#include <sys/resource.h>
#include <sys/random.h>
#include <fcntl.h>
#include <time.h>
#include <signal.h>
#include <errno.h>
typedef int SOCKET;
typedef int FILE_HANDLE;
#define BAD_SOCKET (-1)
#define BAD_FILE (-1)
static FILE_HANDLE log_handle;
static void output(const char *s) { size_t n=slen(s);while(n){ssize_t k=write(1,s,n);if(k<=0)return;s+=k;n-=(size_t)k;} }
static uint64_t now_ms(void) { struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t))return 0;return(uint64_t)t.tv_sec*1000+(uint64_t)t.tv_nsec/1000000; }
static void*allocate(size_t n){return malloc(n);}
static void release(void*p){free(p);}
static int random_bytes(unsigned char*b,size_t n){size_t used=0;while(used<n){ssize_t k=getrandom(b+used,n-used,0);if(k<0&&errno==EINTR)continue;if(k<=0)return 0;used+=(size_t)k;}return 1;}
static FILE_HANDLE open_file(const char *path){int h=open(path,O_RDONLY|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK);struct stat s;if(h<0)return BAD_FILE;if(fstat(h,&s)||!S_ISREG(s.st_mode)){close(h);return BAD_FILE;}return h;}
static uint64_t file_size(FILE_HANDLE h){struct stat s;if(fstat(h,&s)||s.st_size<0)return UINT64_MAX;return(uint64_t)s.st_size;}
static int read_at(FILE_HANDLE h,void*b,size_t n,uint64_t offset){if(offset>INT64_MAX)return-1;return(int)pread(h,b,n,(off_t)offset);}
static void close_file(FILE_HANDLE h){close(h);}
static void close_socket(SOCKET s){close(s);}
static void socket_timeout(SOCKET s){struct timeval t={1,0};setsockopt(s,SOL_SOCKET,SO_RCVTIMEO,&t,sizeof(t));setsockopt(s,SOL_SOCKET,SO_SNDTIMEO,&t,sizeof(t));}
static uint64_t cpu_ms(void){struct rusage u;if(getrusage(RUSAGE_SELF,&u))return 0;return(uint64_t)u.ru_utime.tv_sec*1000+(uint64_t)u.ru_utime.tv_usec/1000+(uint64_t)u.ru_stime.tv_sec*1000+(uint64_t)u.ru_stime.tv_usec/1000;}
static uint64_t peak_rss_bytes(void){struct rusage u;if(getrusage(RUSAGE_SELF,&u))return 0;return(uint64_t)u.ru_maxrss*1024;}
static const char *os_name(void){return "Linux";}
static int socket_init(void){signal(SIGPIPE,SIG_IGN);return 1;}
#endif

#if defined(__aarch64__) || defined(_M_ARM64)
#define ARCH "AArch64"
#elif defined(__x86_64__) || defined(_M_X64)
#define ARCH "x86-64"
#else
#define ARCH "other"
#endif
static int send_all(SOCKET s,const char*b,size_t n){uint64_t deadline=now_ms()+3000;while(n&&now_ms()<deadline){size_t part=n>16384?16384:n;int k=(int)send(s,b,(int)part,0);if(k<=0)return 0;b+=k;n-=(size_t)k;}return n==0;}
static void respond(SOCKET s,unsigned status,const char *body,size_t n,int html){
 char h[2048]="HTTP/1.1 ";number(h,sizeof(h),status);append(h,sizeof(h),status==200?" OK\r\n":" Rejected\r\n");
 append(h,sizeof(h),"Connection: close\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nX-Frame-Options: DENY\r\nReferrer-Policy: no-referrer\r\nCross-Origin-Resource-Policy: same-origin\r\n");
 append(h,sizeof(h),"Content-Security-Policy: default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'\r\n");
 append(h,sizeof(h),"Permissions-Policy: camera=(), microphone=(), geolocation=(), usb=(), serial=()\r\nContent-Type: ");append(h,sizeof(h),html?"text/html; charset=utf-8":"application/json; charset=utf-8");append(h,sizeof(h),"\r\nContent-Length: ");number(h,sizeof(h),n);append(h,sizeof(h),"\r\n\r\n");if(send_all(s,h,slen(h)))send_all(s,body,n);
}
static void reject(SOCKET s,unsigned code){const char*b="{\"error\":\"request denied\",\"read_only\":true}";respond(s,code,b,slen(b),0);}
static size_t snapshot(void){
 failed_buffer=0;response_used=0;response_buffer[0]=0;char *b=response_buffer;size_t cap=sizeof(response_buffer);
 append(b,cap,"{\"schema\":\"living-universe.bridge\",\"version\":1,\"read_only\":true,\"architecture\":\"" ARCH "\",\"host_os\":");json_string(b,cap,(const unsigned char*)os_name(),slen(os_name()));
 append(b,cap,",\"scope\":\"observer process, not the kernel or entire machine\",\"uptime_ms\":");number(b,cap,now_ms()-started);
 append(b,cap,",\"cpu_time_ms\":");number(b,cap,cpu_ms());append(b,cap,",\"requests_handled\":");number(b,cap,requests);
 append(b,cap,",\"peak_rss_bytes\":");uint64_t rss=peak_rss_bytes();if(rss)number(b,cap,rss);else append(b,cap,"null");
 append(b,cap,",\"execution_available\":false,\"filesystem_write_available\":false,\"log_attached\":");append(b,cap,have_log?"true":"false");
 if(have_log){uint64_t size=file_size(log_handle);size_t want=size>LOG_MAX?LOG_MAX:(size_t)size;int n=size==UINT64_MAX?-1:read_at(log_handle,serial_buffer,want,size>want?size-want:0);append(b,cap,",\"log_read_ok\":");append(b,cap,n>=0?"true":"false");append(b,cap,",\"log_tail_only\":");append(b,cap,size>LOG_MAX?"true":"false");append(b,cap,",\"serial_log\":");json_string(b,cap,(unsigned char*)serial_buffer,n>0?(size_t)n:0);}
 append(b,cap,"}");if(failed_buffer){copy(b,cap,"{\"error\":\"response limit\"}");}return slen(b);
}
/* Token and Origin are both checked. Origin is optional for native clients; an
 * unguessable per-launch token is always required for observations. No CORS grant. */
static void handle(SOCKET client){
 socket_timeout(client);size_t used=0;uint64_t deadline=now_ms()+3000;int complete=0;
 while(used+1<sizeof(request_buffer)&&now_ms()<deadline){int n=(int)recv(client,request_buffer+used,(int)(sizeof(request_buffer)-used-1),0);if(n<=0)break;for(int i=0;i<n;i++)if(!request_buffer[used+(size_t)i]){reject(client,400);return;}used+=(size_t)n;request_buffer[used]=0;for(size_t i=3;i<used;i++)if(request_buffer[i-3]=='\r'&&request_buffer[i-2]=='\n'&&request_buffer[i-1]=='\r'&&request_buffer[i]=='\n'){complete=1;if(i+1!=used){reject(client,400);return;}break;}if(complete)break;}
 requests++;if(!complete){reject(client,400);return;}
 char *line=request_buffer,*end=line;while(*end&&!(end[0]=='\r'&&end[1]=='\n'))++end;if(!*end){reject(client,400);return;}*end=0;
 char *path=0;if(slen(line)>4&&line[0]=='G'&&line[1]=='E'&&line[2]=='T'&&line[3]==' ')path=line+4;else{reject(client,405);return;}
 char *space=path;while(*space&&*space!=' ')++space;if(!*space){reject(client,400);return;}*space++=0;if(!eq(space,"HTTP/1.1")){reject(client,400);return;}
 char host[80]="",origin[96]="",key[80]="";unsigned hosts=0,origins=0,keys=0,fields=0;
 line=end+2;
 while(*line&&!(line[0]=='\r'&&line[1]=='\n')){
  if(++fields>64){reject(client,400);return;}end=line;while(*end&&!(end[0]=='\r'&&end[1]=='\n'))++end;if(!*end){reject(client,400);return;}*end=0;
  char *colon=line;while(*colon&&*colon!=':')++colon;if(!*colon||colon==line){reject(client,400);return;}*colon++=0;
  for(char*p=line;*p;p++)if(!((*p>='A'&&*p<='Z')||(*p>='a'&&*p<='z')||(*p>='0'&&*p<='9')||*p=='-')){reject(client,400);return;}
  while(*colon==' '||*colon=='\t') { ++colon; }
  char *tail=colon+slen(colon);
  while(tail>colon&&(tail[-1]==' '||tail[-1]=='\t')) { *--tail=0; }
  for(char*p=colon;*p;p++)if((unsigned char)*p<32||(unsigned char)*p==127){reject(client,400);return;}
  if(ieq(line,"Host")){if(++hosts>1||slen(colon)>=sizeof(host)){reject(client,400);return;}copy(host,sizeof(host),colon);}
  else if(ieq(line,"Origin")){if(++origins>1||slen(colon)>=sizeof(origin)){reject(client,400);return;}copy(origin,sizeof(origin),colon);}
  else if(ieq(line,"X-Universe-Key")){if(++keys>1||slen(colon)>=sizeof(key)){reject(client,400);return;}copy(key,sizeof(key),colon);}
  else if(ieq(line,"Transfer-Encoding")||(ieq(line,"Content-Length")&&!eq(colon,"0"))){reject(client,400);return;}
  line=end+2;
 }
 if(hosts!=1||!eq(host,expected_host)||(origins&&!eq(origin,expected_origin))){reject(client,403);return;}
 if(eq(path,"/")||eq(path,"/LivingUniverse.html")){respond(client,200,(const char*)web_data,web_size,1);return;}
 if(!eq(path,"/api/snapshot")){reject(client,404);return;}
 if(keys!=1||!constant_equal(key,token)){reject(client,403);return;}
 size_t size=snapshot();respond(client,failed_buffer?500:200,response_buffer,size,0);
}
static int run(int argc,char **argv){
 const char *web="LivingUniverse.html",*log=0;
 for(int i=1;i<argc;i++){if(eq(argv[i],"--web")&&i+1<argc)web=argv[++i];else if(eq(argv[i],"--log")&&i+1<argc)log=argv[++i];else if(eq(argv[i],"--port")&&i+1<argc){const char*p=argv[++i];unsigned v=0;if(!*p){output("Invalid port.\n");return 2;}for(;*p;p++){if(*p<'0'||*p>'9'||v>6553){output("Invalid port.\n");return 2;}v=v*10+(unsigned)(*p-'0');}if(v<1024||v>65535){output("Port must be 1024..65535.\n");return 2;}port=v;}else{output("Usage: observer [--web LivingUniverse.html] [--log selected-serial.log] [--port 8765]\n");return 2;}}
 FILE_HANDLE file=open_file(web);if(file==BAD_FILE){output("Cannot open the selected HTML (regular, non-symlink file required).\n");return 2;}
 uint64_t size=file_size(file);if(size==0||size>WEB_MAX){close_file(file);output("HTML must be 1 byte to 4 MiB.\n");return 2;}
 web_size=(size_t)size;web_data=allocate(web_size);if(!web_data){close_file(file);return 2;}
 size_t got=0;while(got<web_size){int n=read_at(file,web_data+got,web_size-got,got);if(n<=0){close_file(file);release(web_data);return 2;}got+=(size_t)n;}close_file(file);
 if(log){log_handle=open_file(log);if(log_handle==BAD_FILE){output("Cannot open the selected regular log file.\n");release(web_data);return 2;}have_log=1;}
 unsigned char random[32];if(!random_bytes(random,sizeof(random))){output("OS randomness unavailable; refusing to start.\n");return 2;}const char*hex="0123456789abcdef";for(unsigned i=0;i<32;i++){token[i*2]=hex[random[i]>>4];token[i*2+1]=hex[random[i]&15];}token[64]=0;
 expected_host[0]=0;append(expected_host,sizeof(expected_host),"127.0.0.1:");number(expected_host,sizeof(expected_host),port);copy(expected_origin,sizeof(expected_origin),"http://");append(expected_origin,sizeof(expected_origin),expected_host);
 if(!socket_init()){output("Socket initialization failed.\n");return 2;}
 SOCKET server=socket(2,1,6);if(server==BAD_SOCKET){output("Cannot create loopback socket.\n");return 2;}
 struct {uint16_t family,port;uint32_t address;unsigned char zero[8];} address;memset(&address,0,sizeof(address));address.family=2;address.port=(uint16_t)((port>>8)|(port<<8));address.address=0x0100007fU;
#ifdef _WIN32
 BOOL exclusive=1;setsockopt(server,0xffff,(int)~4,(const char*)&exclusive,sizeof(exclusive));
#endif
 if(bind(server,(const void*)&address,sizeof(address))||listen(server,8)){close_socket(server);output("Port unavailable. Choose --port with another high port.\n");return 2;}
 started=now_ms();output("Living Universe / native C read-only observer v0.3\nLoopback only. No tool execution or host writes. Ctrl+C stops it.\nOpen this private session URL in your browser:\n");output(expected_origin);output("/#key=");output(token);output("\nDo not share this URL. Select Connect inside the instruments to observe.\n");
 for(;;){SOCKET client=accept(server,0,0);if(client==BAD_SOCKET)continue;handle(client);close_socket(client);}
}
#ifndef _WIN32
int main(int argc,char**argv){return run(argc,argv);}
#else
static char win_args[12][4096];static char*win_argv[12];
void mainCRTStartup(void){int argc=0;WCHAR**args=CommandLineToArgvW(GetCommandLineW(),&argc);if(!args||argc<1||argc>12)ExitProcess(2);for(int i=0;i<argc;i++){if(!WideCharToMultiByte(65001,0,args[i],-1,win_args[i],4096,0,0))ExitProcess(2);win_argv[i]=win_args[i];}LocalFree(args);ExitProcess((unsigned)run(argc,win_argv));}
#endif
