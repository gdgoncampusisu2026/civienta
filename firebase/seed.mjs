import { deleteApp, initializeApp } from 'firebase-admin/app';
import { getAuth } from 'firebase-admin/auth';
import { getFirestore, Timestamp } from 'firebase-admin/firestore';
import config from './firebase.json' with { type: 'json' };
import courses from '../shared/courses.json' with { type: 'json' };
import departments from '../shared/departments.json' with { type: 'json' };
import skills from '../shared/skills.json' with { type: 'json' };

const projectId = 'demo-civienta';
const { auth: authEmulator, firestore: firestoreEmulator } = config.emulators;

// Admin SDK'yi yalnızca yerel emülatörlere yönlendir.
process.env.FIREBASE_AUTH_EMULATOR_HOST = `127.0.0.1:${authEmulator.port}`;
process.env.FIRESTORE_EMULATOR_HOST = `127.0.0.1:${firestoreEmulator.port}`;

const app = initializeApp({ projectId });
const auth = getAuth(app);
const db = getFirestore(app);

const listingIdeas = [
  { title: 'Kampüs etkinlik takvimi', description: 'Kampüs etkinliklerini tek takvimde toplayan bir prototip.' },
  { title: 'Açık ders kaynakları', description: 'Öğrencilerin paylaştığı kaynakları düzenleyen bir katalog.' },
  { title: 'Kulüp tanıtım sitesi', description: 'Kulüp etkinlikleri ve duyuruları için erişilebilir bir site.' },
  { title: 'Gönüllü çalışma grubu', description: 'Öğrencileri kısa süreli gönüllülük çalışmalarında buluşturan bir proje.' },
  { title: 'Kampüs veri panosu', description: 'Örnek kampüs verilerini grafiklerle gösteren bir pano.' },
];
const ownerTypes = ['startup', 'club', 'social'];
const durations = ['short', 'semester', 'long'];
const listingStatuses = ['open', 'open', 'draft', 'closed'];
const noteFormats = [
  { type: 'note', label: 'Ders notu' },
  { type: 'summary', label: 'Konu özeti' },
  { type: 'resource', label: 'Çalışma kaynağı' },
  { type: 'exam', label: 'Deneme soruları' },
];
const skillSlugs = skills.map(({ slug }) => slug);
const now = Timestamp.now();
const dayMs = 24 * 60 * 60 * 1000;
const numberFor = (index) => String(index + 1).padStart(2, '0');

const users = Array.from({ length: 10 }, (_, index) => {
  const number = numberFor(index);
  const account = {
    uid: `fixture-user-${number}`,
    displayName: `Örnek Öğrenci ${number}`,
    email: `ornek.ogrenci${number}@stu.istinye.edu.tr`,
    emailVerified: true,
    password: `civienta-local-fixture-${number}`,
  };
  const data = {
    displayName: account.displayName,
    department: departments[index % departments.length].slug,
    classYear: (index % 4) + 1,
    bio: `Yerel geliştirme için örnek öğrenci profili ${number}.`,
    skills: [skillSlugs[(index * 2) % skillSlugs.length], skillSlugs[(index * 2 + 1) % skillSlugs.length]],
    links: {},
    role: 'student',
    onboarded: index % 5 !== 0,
    createdAt: now,
    updatedAt: now,
  };

  return { account, data };
});

const listings = Array.from({ length: 15 }, (_, index) => {
  const number = numberFor(index);
  const { title, description } = listingIdeas[index % listingIdeas.length];
  const owner = users[index % users.length];
  const status = listingStatuses[index % listingStatuses.length];
  const deadlineDays = status === 'closed' ? -1 : 7 + index;

  return {
    id: `fixture-listing-${number}`,
    data: {
      ownerId: owner.account.uid,
      ownerType: ownerTypes[index % ownerTypes.length],
      orgName: `Örnek Kampüs Ekibi ${number}`,
      title: `${title} (${number})`,
      description,
      requiredSkills: [owner.data.skills[0]],
      niceToHaveSkills: [owner.data.skills[1]],
      duration: durations[index % durations.length],
      weeklyHours: (index % 5) + 2,
      slots: (index % 3) + 1,
      deadline: Timestamp.fromMillis(now.toMillis() + deadlineDays * dayMs),
      status,
      applicantCount: 0,
      createdAt: now,
      updatedAt: now,
    },
  };
});

const notes = Array.from({ length: 20 }, (_, index) => {
  const courseIndex = Math.floor(index / noteFormats.length);
  const course = courses[courseIndex % courses.length];
  const { type, label } = noteFormats[index % noteFormats.length];
  const uploader = users[index % users.length];
  const id = `fixture-note-${numberFor(index)}`;

  return {
    id,
    data: {
      uploaderId: uploader.account.uid,
      uploaderName: uploader.account.displayName,
      department: course.department,
      courseCode: course.slug,
      title: `${course.label} — ${label}`,
      description: `Yerel geliştirme için örnek ${label.toLowerCase()} kaydı.`,
      type,
      url: `https://civienta.example.invalid/notes/${id}`,
      source: 'other',
      likeCount: 0,
      reportCount: 0,
      status: 'published',
      createdAt: now,
    },
  };
});

async function ensureAuthUser(account) {
  try {
    await auth.createUser(account);
  } catch (error) {
    if (error.code !== 'auth/uid-already-exists') throw error;

    const existing = await auth.getUser(account.uid);
    if (existing.email !== account.email) throw error;
  }
}

try {
  for (const { account } of users) await ensureAuthUser(account);

  const documents = new Map([
    ...users.map(({ account, data }) => [`users/${account.uid}`, data]),
    ...listings.map(({ id, data }) => [`listings/${id}`, data]),
    ...notes.map(({ id, data }) => [`notes/${id}`, data]),
  ]);

  await db.runTransaction(async (transaction) => {
    const references = [...documents.keys()].map((path) => db.doc(path));
    const snapshots = await transaction.getAll(...references);
    for (const snapshot of snapshots) {
      if (!snapshot.exists) transaction.create(snapshot.ref, documents.get(snapshot.ref.path));
    }
  });

  console.log(`Örnek veriler hazır: ${users.length} kullanıcı, ${listings.length} ilan, ${notes.length} not.`);
} catch (error) {
  console.error('Örnek veriler yüklenemedi. Yerel emülatörlerin açık olduğunu kontrol edin.');
  console.error(error.message);
  process.exitCode = 1;
} finally {
  await deleteApp(app);
}
