#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <nfc/nfc.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>

static void
sprint_hex(char *buf,size_t buflen,
	   const uint8_t *pbtData, const size_t szBytes)
{
  size_t szPos;
 
  for (szPos = 0; szPos < szBytes; szPos++) {
    snprintf(buf,buflen,"%02x", pbtData[szPos]);
    buf=buf+2;
    buflen=buflen-2;
  }
  buf[0]=0;
}

static void
bridge(const char *connstring)
{
  nfc_device *pnd;
  nfc_target nt[10];
  int u;
  struct sockaddr_in addr,dest;
  int count,i;
  char buf[1024];
  char *b;

  nfc_context *context;

  nfc_init(&context);
  if (context == NULL) {
    fprintf(stderr,"Unable to init libnfc (malloc)\n");
    exit(EXIT_FAILURE);
  }

  pnd = nfc_open(context, connstring);
 
  if (pnd == NULL) {
    if (connstring == NULL) {
      fprintf(stderr,"ERROR: Unable to open any NFC device.\n");
    } else {
      fprintf(stderr,"ERROR: Unable to open NFC device '%s'.\n",connstring);
    }
    exit(EXIT_FAILURE);
  }

  if (nfc_initiator_init(pnd) < 0) {
    nfc_perror(pnd, "nfc_initiator_init");
    exit(EXIT_FAILURE);
  }
 
#if 0
  printf("NFC reader: %s opened\n", nfc_device_get_name(pnd));
#endif /* 0 */

  if ((u=socket(AF_INET, SOCK_DGRAM, 0))<0) {
    perror("cannot create socket");
    exit(EXIT_FAILURE);
  }

  memset(&addr,0,sizeof(addr));
  addr.sin_family=AF_INET;
  addr.sin_addr.s_addr=htonl(INADDR_ANY);
  addr.sin_port=htons(0);
  if (bind(u,(struct sockaddr *)&addr,sizeof(addr))<0) {
    perror("bind failed");
    exit(EXIT_FAILURE);
  }

  memset(&dest,0,sizeof(dest));
  dest.sin_family=AF_INET;
  dest.sin_addr.s_addr=htonl(0x7f000001);
  dest.sin_port=htons(8455);

  const nfc_modulation nmMifare = {
    .nmt = NMT_ISO14443A,
    .nbr = NBR_106,
  };
  count=1;
  while (count>=0) {
    count=nfc_initiator_list_passive_targets(pnd, nmMifare, nt, 10);
    if (count>0) {
      for (i=0; i<count; i++) {
	b=buf;
	strcpy(b,"nfc:");
	b=b+4;
	sprint_hex(b,sizeof(buf)-4,
		   nt[i].nti.nai.abtUid, nt[i].nti.nai.szUidLen);
	sendto(u,buf,strlen(buf),0,(struct sockaddr *)&dest,sizeof(dest));
      }
    }
    usleep(125000);
  }

  nfc_close(pnd);
  nfc_exit(context);
  exit(EXIT_SUCCESS);
}

static void list(void)
{
  nfc_context *context;
  nfc_connstring ncs[10];
  size_t number_found;
  int i;

  nfc_init(&context);
  if (context == NULL) {
    fprintf(stderr,"Unable to init libnfc (malloc)\n");
    exit(EXIT_FAILURE);
  }

  number_found=nfc_list_devices(context,ncs,10);
  printf("%zu devices found:\n",number_found);
  for (i=0; i<number_found; i++) {
    printf("%s\n",ncs[i]);
  }

  nfc_exit(context);
}

int main(int argc, const char *argv[])
{
  if (argc < 2) bridge(NULL);
  else if (argc == 2) {
    if (strcmp(argv[1],"-l")==0) {
      list();
    } else {
      bridge(argv[1]);
    }
  }
  else {
    printf("Usage: %s -l | connection string\n",argv[0]);
  }
  exit(EXIT_SUCCESS);
}
