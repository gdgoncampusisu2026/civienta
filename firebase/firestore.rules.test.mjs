import assert from 'node:assert/strict';
import { after, before, beforeEach, test } from 'node:test';
import { assertFails, assertSucceeds, initializeTestEnvironment } from '@firebase/rules-unit-testing';
import { collection, deleteDoc, deleteField, doc, getDoc, getDocs, setDoc, updateDoc } from 'firebase/firestore';
import config from './firebase.json' with { type: 'json' };

const ownerId = 'fixture-owner';
const otherId = 'fixture-other';
const newUserId = 'fixture-new';
const ownerEmail = 'ornek.sahip@stu.istinye.edu.tr';
const ownerProfile = { displayName: 'Örnek Öğrenci', email: ownerEmail, role: 'student' };
const newProfile = { displayName: 'Örnek Yeni Öğrenci' };

let environment;

function schoolAccount(uid = ownerId) {
  return environment.authenticatedContext(uid, { email: ownerEmail, email_verified: true }).firestore();
}

before(async () => {
  environment = await initializeTestEnvironment({
    projectId: 'demo-civienta',
    firestore: config.emulators.firestore,
  });
});

beforeEach(async () => {
  await environment.clearFirestore();
  await environment.withSecurityRulesDisabled(async (context) => {
    await setDoc(doc(context.firestore(), 'users', ownerId), ownerProfile);
  });
});

after(async () => {
  await environment?.cleanup();
});

test('doğrulanmış okul hesabı profil okuyabilir ve profilleri listeleyebilir', async () => {
  const db = schoolAccount(otherId);
  const profile = await assertSucceeds(getDoc(doc(db, 'users', ownerId)));
  assert.deepEqual(profile.data(), ownerProfile);
  const users = await assertSucceeds(getDocs(collection(db, 'users')));
  assert.equal(users.size, 1);
});

test('oturum açmayan kullanıcı profilleri okuyamaz veya listeleyemez', async () => {
  const db = environment.unauthenticatedContext().firestore();
  await assertFails(getDoc(doc(db, 'users', ownerId)));
  await assertFails(getDocs(collection(db, 'users')));
});

const invalidSchoolAccounts = [
  ['farklı alan adı', { email: 'ornek.sahip@example.invalid', email_verified: true }],
  ['benzer alan adı', { email: 'ornek.sahip@notstu.istinye.edu.tr', email_verified: true }],
  ['alan adından sonra ek', { email: 'ornek.sahip@stu.istinye.edu.tr.example.invalid', email_verified: true }],
  ['doğrulanmamış e-posta', { email: ownerEmail, email_verified: false }],
  ['eksik doğrulama alanı', { email: ownerEmail }],
  ['eksik e-posta', { email_verified: true }],
];

for (const [description, claims] of invalidSchoolAccounts) {
  test(`okul hesabı okuması reddedilir (${description})`, async () => {
    const db = environment.authenticatedContext(ownerId, claims).firestore();
    await assertFails(getDoc(doc(db, 'users', ownerId)));
    await assertFails(getDocs(collection(db, 'users')));
  });
}

test('sahip, korunan alanlar olmadan kendi profilini oluşturabilir', async () => {
  const profile = doc(schoolAccount(newUserId), 'users', newUserId);
  await assertSucceeds(setDoc(profile, newProfile));
  assert.deepEqual((await getDoc(profile)).data(), newProfile);
});

test('sahip kendi profilindeki düzenlenebilir alanları güncelleyebilir', async () => {
  const profile = doc(schoolAccount(), 'users', ownerId);
  await assertSucceeds(updateDoc(profile, { bio: 'Örnek biyografi' }));
  assert.deepEqual((await getDoc(profile)).data(), { ...ownerProfile, bio: 'Örnek biyografi' });
});

test('başka kullanıcı profil oluşturamaz veya güncelleyemez', async () => {
  const db = schoolAccount(otherId);
  await assertFails(setDoc(doc(db, 'users', newUserId), newProfile));
  await assertFails(updateDoc(doc(db, 'users', ownerId), { bio: 'Örnek biyografi' }));
});

test('oturum açmayan kullanıcı profil oluşturamaz veya güncelleyemez', async () => {
  const db = environment.unauthenticatedContext().firestore();
  await assertFails(setDoc(doc(db, 'users', newUserId), newProfile));
  await assertFails(updateDoc(doc(db, 'users', ownerId), { bio: 'Örnek biyografi' }));
});

for (const [field, value] of [['role', 'admin'], ['email', 'ornek.degisiklik@stu.istinye.edu.tr']]) {
  test(`sahip profil oluştururken ${field} yazamaz`, async () => {
    const profile = doc(schoolAccount(newUserId), 'users', newUserId);
    await assertFails(setDoc(profile, { ...newProfile, [field]: value }));
  });

  test(`sahip mevcut ${field} alanını değiştiremez veya silemez`, async () => {
    const profile = doc(schoolAccount(), 'users', ownerId);
    await assertFails(updateDoc(profile, { [field]: value }));
    await assertFails(updateDoc(profile, { [field]: deleteField() }));
  });

  test(`sahip yeni bir profile sonradan ${field} ekleyemez`, async () => {
    const profile = doc(schoolAccount(newUserId), 'users', newUserId);
    await assertSucceeds(setDoc(profile, newProfile));
    await assertFails(updateDoc(profile, { [field]: value }));
  });
}

test('istemci korunan alanları içeren profilin üzerine yazamaz veya profili silemez', async () => {
  const profile = doc(schoolAccount(), 'users', ownerId);
  await assertFails(setDoc(profile, newProfile));
  await assertFails(deleteDoc(profile));
});

const blockedPaths = [
  'listings/fixture-listing',
  'applications/fixture-application',
  'notes/fixture-note',
  `notes/fixture-note/likes/${ownerId}`,
  `notes/fixture-note/reports/${ownerId}`,
  'listingVectors/fixture-listing',
  `userVectors/${ownerId}`,
  'unknown/fixture-document',
];

for (const path of blockedPaths) {
  test(`diğer koleksiyonlarda okuma ve yazma reddedilir (${path})`, async () => {
    const document = doc(schoolAccount(), path);
    await assertFails(getDoc(document));
    await assertFails(setDoc(document, { fixture: true }));
  });
}
